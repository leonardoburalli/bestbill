"""Mercato libero EE XML -> Offer, streaming (xml.etree.ElementTree.iterparse).

Namespace: ``http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01``.
See docs/arera-data.md for the code tables and
:mod:`bestbill.arera.policy` for the pricing rules used here.

Domestic only (``TIPO_CLIENTE`` != domestic is excluded and counted, like
any other unsupported structure). Dual-fuel offers (``OFFERTA_SINGOLA`` ==
"NO") are excluded and counted: the engine only prices single-commodity
(electricity) offers.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime

from bestbill.arera import policy
from bestbill.arera.codes import TipologiaFasce
from bestbill.arera.operators import Operator, website_domain, zero_pad_vat
from bestbill.arera.parameters import Parameters
from bestbill.core.models import (
    BandStructure,
    ConsumptionTier,
    CustomerType,
    Discount,
    DiscountUnit,
    GeoRestriction,
    Offer,
    OfferSource,
    PriceType,
    Residency,
    SupplierNameSource,
)

_NS = "{http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01}"

#: Sconto/PrezziSconto/TIPOLOGIA code meaning "discount on Maggior Tutela".
_SCONTO_TIPOLOGIA_MAGGIOR_TUTELA = "04"


def _resolve_supplier_name(
    piva_raw: str,
    url_sito_venditore: str | None,
    operators: dict[str, Operator],
    placet_names: dict[str, str],
) -> tuple[str, str | None, SupplierNameSource | None]:
    """Resolve a mercato libero offer's display supplier name, in order:
    the ARERA "Ricerca operatori" export (by VAT) -> a PLACET row's
    ``denominazione`` for the same VAT -> the retailer's website domain
    (``URL_SITO_VENDITORE``) -> ``"P.IVA <vat>"``. Returns ``(name, vat,
    source)``; ``vat`` and ``source`` are ``None`` if PIVA_UTENTE itself
    is missing (there's nothing to resolve against).
    """
    vat = zero_pad_vat(piva_raw) if piva_raw else None
    if vat is not None:
        operator = operators.get(vat)
        if operator is not None:
            return operator.name, vat, SupplierNameSource.ARERA
        placet_name = placet_names.get(vat)
        if placet_name:
            return placet_name, vat, SupplierNameSource.PLACET
    domain = website_domain(url_sito_venditore)
    if domain is not None:
        return domain, vat, SupplierNameSource.DOMAIN
    if vat is not None:
        return f"P.IVA {vat}", vat, SupplierNameSource.VAT
    return "sconosciuto", None, None


class MliberoFormatError(ValueError):
    """The mercato libero XML doesn't match the expected structure."""


@dataclass(frozen=True)
class Excluded:
    row_id: str
    reason: str


ParsedOffer = Offer | Excluded

_FASCIA_MAPS: dict[str, dict[str, str]] = {
    TipologiaFasce.MONO: {"01": "mono"},
    TipologiaFasce.F1F2F3: {"01": "F1", "02": "F2", "03": "F3"},
    TipologiaFasce.F1F23: {"01": "F1", "91": "F23"},
}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(f"{_NS}{tag}")
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _all_texts(el: ET.Element, tag: str) -> list[str]:
    return [c.text.strip() for c in el.findall(f"{_NS}{tag}") if c.text]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _parse_validity_date(value: str | None) -> date | None:
    if value is None:
        return None
    # dd/mm/YYYY_HH:MM:SS
    return datetime.strptime(value, "%d/%m/%Y_%H:%M:%S").date()


def _geo(el: ET.Element) -> GeoRestriction | None:
    zone = el.find(f"{_NS}ZoneOfferta")
    if zone is None:
        return None
    regioni = frozenset(_all_texts(zone, "REGIONE"))
    province = frozenset(_all_texts(zone, "PROVINCIA"))
    comuni = frozenset(_all_texts(zone, "COMUNE"))
    if not regioni and not province and not comuni:
        return None
    return GeoRestriction(regioni=regioni, province=province, comuni=comuni)


def _residency(el: ET.Element) -> Residency:
    code = _text(el, "DOMESTICO_RESIDENTE")
    if code is None:
        return Residency.ANY
    return {
        "01": Residency.RESIDENTS,
        "02": Residency.NON_RESIDENTS,
        "03": Residency.ANY,
    }.get(code, Residency.ANY)


#: IntervalloPrezzi child tags this importer understands. Anything else
#: (e.g. PeriodoValidita) excludes the whole offer via
#: ``_interval_unknown_tags`` -- see the module's guardrail policy.
_INTERVALLO_KNOWN_TAGS = frozenset(
    {"PREZZO", "UNITA_MISURA", "FASCIA_COMPONENTE", "CONSUMO_DA", "CONSUMO_A"}
)


def _interval_unknown_tags(interval: ET.Element) -> list[str]:
    return sorted({_local(c.tag) for c in interval} - _INTERVALLO_KNOWN_TAGS)


def _parse_componenti(
    el: ET.Element, price_type: PriceType, tipologia_fasce: str
) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, list[tuple[float, float | None, float]]],
    dict[str, list[tuple[float, float | None, float]]],
    float,
    float,
    float,
    str | None,
]:
    """Returns (energy_price, spread, energy_tier_rows, spread_tier_rows,
    per_kwh_extras, fixed_fee, one_off, exclusion_reason). The tier rows
    are raw (CONSUMO_DA, CONSUMO_A, PREZZO) tuples per band, still to be
    validated by ``policy.build_consumption_tiers``.
    """
    energy_price: dict[str, float] = {}
    spread: dict[str, float] = {}
    energy_tier_rows: dict[str, list[tuple[float, float | None, float]]] = {}
    spread_tier_rows: dict[str, list[tuple[float, float | None, float]]] = {}
    extras_values: list[float] = []
    fixed_fee = 0.0
    one_off = 0.0
    fasce_map = _FASCIA_MAPS.get(tipologia_fasce, {})

    for comp in el.findall(f"{_NS}ComponenteImpresa"):
        macroarea = _text(comp, "MACROAREA")
        intervals = comp.findall(f"{_NS}IntervalloPrezzi")
        if macroarea is None or not intervals:
            continue
        for interval in intervals:
            unknown_tags = _interval_unknown_tags(interval)
            if unknown_tags:
                unknown_reason = (
                    "elemento di prezzo non gestito: "
                    f"IntervalloPrezzi/{unknown_tags[0]}"
                )
                return {}, {}, {}, {}, 0.0, 0.0, 0.0, unknown_reason
            unita = _text(interval, "UNITA_MISURA")
            prezzo = _to_float(_text(interval, "PREZZO"))
            if unita is None or prezzo is None:
                continue
            consumo_da = _to_float(_text(interval, "CONSUMO_DA"))
            consumo_a = _to_float(_text(interval, "CONSUMO_A"))
            role, reason = policy.classify_component(macroarea, unita, price_type)
            if role is None:
                return {}, {}, {}, {}, 0.0, 0.0, 0.0, reason
            if consumo_da is not None and role not in (
                policy.ComponentRole.ENERGY_PRICE,
                policy.ComponentRole.SPREAD,
            ):
                # Per-kWh extras aren't banded in the model and fixed/power/
                # one-off fees aren't kWh-scaled at all -- tiering them is
                # ambiguous, so exclude rather than guess (docs/arera-data.md).
                return (
                    {},
                    {},
                    {},
                    {},
                    0.0,
                    0.0,
                    0.0,
                    policy.UNSUPPORTED_TIERED_PRICE_REASON,
                )
            if role == policy.ComponentRole.FIXED_FEE:
                fixed_fee += prezzo
            elif role == policy.ComponentRole.ONE_OFF:
                one_off += prezzo
            elif role == policy.ComponentRole.POWER_FEE:
                fixed_fee += 0.0  # handled by caller via a dedicated pass
            elif role == policy.ComponentRole.PER_KWH_EXTRAS:
                extras_values.append(prezzo)
            elif role in (
                policy.ComponentRole.ENERGY_PRICE,
                policy.ComponentRole.SPREAD,
            ):
                fascia = _text(interval, "FASCIA_COMPONENTE")
                band = (
                    fasce_map.get(fascia)
                    if fascia is not None
                    else ("mono" if tipologia_fasce == TipologiaFasce.MONO else None)
                )
                if band is None:
                    return (
                        {},
                        {},
                        {},
                        {},
                        0.0,
                        0.0,
                        0.0,
                        (
                            f"FASCIA_COMPONENTE {fascia!r} non mappabile per "
                            f"TIPOLOGIA_FASCE {tipologia_fasce!r}"
                        ),
                    )
                if consumo_da is not None:
                    tier_rows = (
                        energy_tier_rows
                        if role == policy.ComponentRole.ENERGY_PRICE
                        else spread_tier_rows
                    )
                    tier_rows.setdefault(band, []).append(
                        (consumo_da, consumo_a, prezzo)
                    )
                else:
                    target = (
                        energy_price
                        if role == policy.ComponentRole.ENERGY_PRICE
                        else spread
                    )
                    target[band] = target.get(band, 0.0) + prezzo

    extras = sum(extras_values) / len(extras_values) if extras_values else 0.0
    return (
        energy_price,
        spread,
        energy_tier_rows,
        spread_tier_rows,
        extras,
        fixed_fee,
        one_off,
        None,
    )


def _power_fee(el: ET.Element) -> float:
    total = 0.0
    for comp in el.findall(f"{_NS}ComponenteImpresa"):
        for interval in comp.findall(f"{_NS}IntervalloPrezzi"):
            unita = _text(interval, "UNITA_MISURA")
            prezzo = _to_float(_text(interval, "PREZZO"))
            if unita == "02" and prezzo is not None:
                total += prezzo
    return total


def _dispatching(
    el: ET.Element, params: Parameters
) -> tuple[policy.DispatchingResult, None] | tuple[None, str]:
    """Combine every Dispacciamento row on the offer (additive by
    construction). Returns an exclusion reason if any row is Maggior
    Tutela, reserved for non-domestic offers, or missing a parameter.
    """
    results: list[policy.DispatchingResult] = []
    for disp in el.findall(f"{_NS}Dispacciamento"):
        tipo = _text(disp, "TIPO_DISPACCIAMENTO")
        valore = _to_float(_text(disp, "VALORE_DISP"))
        if tipo is None:
            continue
        result, reason = policy.dispatching_component_v2(tipo, valore, params)
        if result is None:
            assert reason is not None
            return None, reason
        results.append(result)
    return policy.combine_dispatching(results), None


#: Sconto direct child tags this importer understands. CODICE_COMPONENTE_FASCIA
#: (per-band discount targeting) isn't implemented -- see the module's
#: guardrail policy.
_SCONTO_KNOWN_CHILD_TAGS = frozenset(
    {
        "NOME",
        "DESCRIZIONE",
        "VALIDITA",
        "IVA_SCONTO",
        "Condizione",
        "PrezziSconto",
        "PeriodoValidita",
    }
)

#: PrezziSconto child tags this importer understands.
_PREZZI_SCONTO_KNOWN_TAGS = frozenset(
    {"TIPOLOGIA", "UNITA_MISURA", "PREZZO", "VALIDO_DA", "VALIDO_FINO"}
)


def _parse_period_duration(sconto: ET.Element) -> tuple[int | None, str | None]:
    """Parse Sconto/PeriodoValidita/DURATA (whole months from activation,
    the only form observed on a priced -- unconditional, on-entry/within-
    12-months -- domestic Sconto in the real catalogue). VALIDO_FINO
    (calendar month) and MESE_VALIDITA restrict validity to a specific
    calendar window that doesn't map onto this engine's rolling 12-month
    estimate unambiguously, so the caller excludes the whole offer rather
    than guess.
    """
    periodo = sconto.find(f"{_NS}PeriodoValidita")
    if periodo is None:
        return None, None
    for child in periodo:
        tag = _local(child.tag)
        if tag != "DURATA":
            return (
                None,
                f"elemento di prezzo non gestito: Sconto/PeriodoValidita/{tag}",
            )
    durata = _text(periodo, "DURATA")
    if durata is None:
        return None, None
    return int(float(durata)), None


def _parse_discounts(
    el: ET.Element,
) -> tuple[list[Discount], str | None]:
    """Returns ``(discounts, exclusion_reason)``; a Sconto/PrezziSconto
    TIPOLOGIA 04 (Maggior Tutela) excludes the whole offer.
    """
    discounts: list[Discount] = []
    for sconto in el.findall(f"{_NS}Sconto"):
        name = _text(sconto, "NOME") or ""
        description = _text(sconto, "DESCRIZIONE") or ""
        validita_code = _text(sconto, "VALIDITA")
        if validita_code is None:
            continue
        validity = policy.sconto_validita_to_model(validita_code)
        condizione = sconto.find(f"{_NS}Condizione")
        condizione_code = (
            _text(condizione, "CONDIZIONE_APPLICAZIONE")
            if condizione is not None
            else None
        )
        conditional = condizione_code != "00"
        would_be_priced = policy.discount_is_priced(validity, conditional)

        duration_months: int | None = None
        if would_be_priced:
            unknown_tags = sorted(
                {_local(c.tag) for c in sconto} - _SCONTO_KNOWN_CHILD_TAGS
            )
            if unknown_tags:
                return [], f"elemento di prezzo non gestito: Sconto/{unknown_tags[0]}"
            duration_months, duration_reason = _parse_period_duration(sconto)
            if duration_reason is not None:
                return [], duration_reason

        iva_code = _text(sconto, "IVA_SCONTO")
        for prezzo_sconto in sconto.findall(f"{_NS}PrezziSconto"):
            tipologia = _text(prezzo_sconto, "TIPOLOGIA")
            if tipologia == _SCONTO_TIPOLOGIA_MAGGIOR_TUTELA:
                return [], policy.MAGGIOR_TUTELA_REASON
            if would_be_priced:
                unknown_ps_tags = sorted(
                    {_local(c.tag) for c in prezzo_sconto} - _PREZZI_SCONTO_KNOWN_TAGS
                )
                if unknown_ps_tags:
                    return [], (
                        "elemento di prezzo non gestito: "
                        f"PrezziSconto/{unknown_ps_tags[0]}"
                    )
            unita = _text(prezzo_sconto, "UNITA_MISURA")
            prezzo = _to_float(_text(prezzo_sconto, "PREZZO"))
            if unita is None or prezzo is None:
                continue
            discount_unit = policy.unita_misura_to_discount_unit(unita)
            consumption_from_kwh = None
            consumption_to_kwh = None
            if discount_unit is DiscountUnit.EUR_KWH:
                consumption_from_kwh = _to_float(_text(prezzo_sconto, "VALIDO_DA"))
                consumption_to_kwh = _to_float(_text(prezzo_sconto, "VALIDO_FINO"))
            elif duration_months is not None:
                # DURATA was only ever observed on €/kWh discounts; a
                # month-limited discount in another unit is ambiguous
                # (prorate the lump sum? apply it in full regardless?).
                return [], (
                    "Sconto/PeriodoValidita/DURATA non supportata per unità "
                    f"diversa da €/kWh: {discount_unit!r}"
                )
            amount_pre_vat = policy.discount_nominal_to_pre_vat(prezzo, iva_code)
            instalments = (
                policy.resolve_instalments(
                    description, discount_unit, prezzo, amount_pre_vat
                )
                if would_be_priced
                else None
            )
            discounts.append(
                Discount(
                    name=name,
                    description=description,
                    validity=validity,
                    conditional=conditional,
                    amount=amount_pre_vat,
                    unit=discount_unit,
                    instalment_months=instalments.months if instalments else None,
                    instalment_amount_eur=instalments.amount if instalments else None,
                    instalment_every_months=(
                        instalments.every_months if instalments else 1
                    ),
                    applies_before_vat=True,
                    consumption_from_kwh=consumption_from_kwh,
                    consumption_to_kwh=consumption_to_kwh,
                    duration_months=(
                        duration_months
                        if discount_unit is DiscountUnit.EUR_KWH
                        else None
                    ),
                )
            )
    return discounts, None


def _band_structure_from_tipologia(code: str) -> BandStructure:
    return {
        TipologiaFasce.MONO: BandStructure.MONO,
        TipologiaFasce.F1F2F3: BandStructure.F1F2F3,
        TipologiaFasce.F1F23: BandStructure.F1F23,
    }[TipologiaFasce(code)]


def parse_offerta(
    el: ET.Element,
    params: Parameters,
    operators: dict[str, Operator] | None = None,
    placet_names: dict[str, str] | None = None,
) -> ParsedOffer:
    """Parse one ``<offerta>`` element into an :class:`Excluded` (unsupported
    structure, non-domestic, or any other unpriceable case -- always
    counted, never silently dropped) or an :class:`Offer`.

    ``operators`` (the ARERA "Ricerca operatori" export, VAT -> name) and
    ``placet_names`` (VAT -> PLACET ``denominazione``) resolve the
    supplier display name, since the XML itself only carries
    ``PIVA_UTENTE`` -- see ``_resolve_supplier_name`` and
    ``bestbill.catalog.build``.
    """
    operators = operators if operators is not None else {}
    placet_names = placet_names if placet_names is not None else {}
    ident = el.find(f"{_NS}IdentificativiOfferta")
    offer_id = _text(ident, "COD_OFFERTA") if ident is not None else None
    if offer_id is None:
        return Excluded("?", "COD_OFFERTA mancante")

    dettaglio = el.find(f"{_NS}DettaglioOfferta")
    if dettaglio is None:
        return Excluded(offer_id, "DettaglioOfferta mancante")

    tipo_cliente_code = _text(dettaglio, "TIPO_CLIENTE")
    if tipo_cliente_code != "01":
        # BestBill only compares household offers (docs/pricing-policy.md);
        # non-domestic offers are excluded and counted, never silently
        # dropped, so the catalogue never contains one.
        return Excluded(
            offer_id, f"offerta non domestica (TIPO_CLIENTE={tipo_cliente_code!r})"
        )

    offerta_singola = _text(dettaglio, "OFFERTA_SINGOLA")
    if offerta_singola == "NO":
        return Excluded(
            offer_id, "offerta dual-fuel (OFFERTA_SINGOLA=NO), fuori scope MVP"
        )

    tipo_offerta_code = _text(dettaglio, "TIPO_OFFERTA")
    if tipo_offerta_code == "01":
        price_type = PriceType.FIXED
    elif tipo_offerta_code == "02":
        price_type = PriceType.VARIABLE
    else:
        return Excluded(offer_id, f"TIPO_OFFERTA non supportato: {tipo_offerta_code!r}")

    if price_type is PriceType.VARIABLE:
        riferimenti = el.findall(f"{_NS}RiferimentiPrezzoEnergia")
        if len(riferimenti) > 1:
            return Excluded(
                offer_id, "più indici di riferimento prezzo energia non supportati"
            )
        idx_el = riferimenti[0] if riferimenti else None
        idx_code = _text(idx_el, "IDX_PREZZO_ENERGIA") if idx_el is not None else None
        if idx_code is not None and policy.idx_is_maggior_tutela(idx_code):
            return Excluded(offer_id, policy.MAGGIOR_TUTELA_REASON)
        if idx_code is None or not policy.idx_is_supported(idx_code):
            return Excluded(
                offer_id, f"IDX_PREZZO_ENERGIA non supportato: {idx_code!r}"
            )
        coefficiente = _text(idx_el, "COEFFICIENTE") if idx_el is not None else None
        if coefficiente is not None and coefficiente != policy.SUPPORTED_COEFFICIENTE:
            return Excluded(offer_id, f"COEFFICIENTE {coefficiente!r} non supportato")

    tipo_prezzo = el.find(f"{_NS}TipoPrezzo")
    tipologia_fasce = (
        _text(tipo_prezzo, "TIPOLOGIA_FASCE") if tipo_prezzo is not None else None
    )
    if tipologia_fasce is None or not policy.tipologia_fasce_is_supported(
        tipologia_fasce
    ):
        return Excluded(
            offer_id, f"TIPOLOGIA_FASCE non supportata: {tipologia_fasce!r}"
        )
    band_structure = _band_structure_from_tipologia(tipologia_fasce)

    (
        energy_price,
        spread,
        energy_tier_rows,
        spread_tier_rows,
        extras,
        fixed_fee,
        one_off,
        reason,
    ) = _parse_componenti(el, price_type, tipologia_fasce)
    if reason is not None:
        return Excluded(offer_id, reason)

    energy_price_tiers: dict[str, list[ConsumptionTier]] = {}
    for band, rows in energy_tier_rows.items():
        tiers, tier_reason = policy.build_consumption_tiers(rows)
        if tier_reason is not None:
            return Excluded(offer_id, tier_reason)
        assert tiers is not None
        energy_price_tiers[band] = tiers
    spread_tiers: dict[str, list[ConsumptionTier]] = {}
    for band, rows in spread_tier_rows.items():
        tiers, tier_reason = policy.build_consumption_tiers(rows)
        if tier_reason is not None:
            return Excluded(offer_id, tier_reason)
        assert tiers is not None
        spread_tiers[band] = tiers

    dispatching_result, disp_reason = _dispatching(el, params)
    if dispatching_result is None:
        assert disp_reason is not None
        return Excluded(offer_id, disp_reason)
    power_fee = _power_fee(el)

    discounts, discount_reason = _parse_discounts(el)
    if discount_reason is not None:
        return Excluded(offer_id, discount_reason)

    expected_keys = (
        {"mono"}
        if band_structure is BandStructure.MONO
        else (
            {"F1", "F2", "F3"}
            if band_structure is BandStructure.F1F2F3
            else {"F1", "F23"}
        )
    )
    if price_type is PriceType.FIXED:
        combined_energy_keys = set(energy_price) | set(energy_price_tiers)
        if not combined_energy_keys and band_structure is BandStructure.MONO:
            # No MACROAREA 04/06 (energy price) component at all: the whole
            # energy price was filed under MACROAREA 02 instead (observed on
            # real offers, e.g. "Prezzo Energia Fisso" -- docs/arera-data.md),
            # already priced via per_kwh_extras_eur on total kWh with no
            # losses -- the same cost a mono energy_price would produce.
            # Only safe for MONO: a banded (F1/F2/F3) MACROAREA 02-only offer
            # would need band-weighted extras, not this flat average, so it
            # still excludes below.
            energy_price = {"mono": 0.0}
        elif combined_energy_keys != expected_keys:
            return Excluded(
                offer_id,
                f"prezzi energia incompleti per {band_structure!r}: "
                f"{sorted(combined_energy_keys)}",
            )
        else:
            for key in expected_keys - set(energy_price):
                energy_price[key] = 0.0
    if not spread:
        spread = dict.fromkeys(expected_keys, 0.0)
    elif set(spread) != expected_keys:
        for key in expected_keys - set(spread):
            spread[key] = 0.0

    validita = el.find(f"{_NS}ValiditaOfferta")
    valid_from = (
        _parse_validity_date(_text(validita, "DATA_INIZIO"))
        if validita is not None
        else None
    )
    valid_to = (
        _parse_validity_date(_text(validita, "DATA_FINE"))
        if validita is not None
        else None
    )

    caratteristiche = el.find(f"{_NS}CaratteristicheOfferta")
    consumo_min = (
        _to_float(_text(caratteristiche, "CONSUMO_MIN"))
        if caratteristiche is not None
        else None
    )
    consumo_max = (
        _to_float(_text(caratteristiche, "CONSUMO_MAX"))
        if caratteristiche is not None
        else None
    )

    duration_months, duration_open_ended = policy.parse_durata(
        _text(dettaglio, "DURATA")
    )

    contatti = dettaglio.find(f"{_NS}Contatti")
    url = None
    url_sito_venditore = None
    if contatti is not None:
        url = _text(contatti, "URL_OFFERTA") or _text(contatti, "URL_SITO_VENDITORE")
        url_sito_venditore = _text(contatti, "URL_SITO_VENDITORE")

    try:
        piva = (
            (ident.findtext(f"{_NS}PIVA_UTENTE") or "").strip()
            if ident is not None
            else ""
        )
        supplier_name, supplier_vat, supplier_name_source = _resolve_supplier_name(
            piva, url_sito_venditore, operators, placet_names
        )
        offer = Offer(
            id=offer_id,
            supplier=supplier_name,
            name=_text(dettaglio, "NOME_OFFERTA") or offer_id,
            url=url,
            source=OfferSource.MLIBERO,
            price_type=price_type,
            band_structure=band_structure,
            energy_price_eur_kwh=energy_price if price_type is PriceType.FIXED else {},
            spread_eur_kwh=spread,
            energy_price_tiers_eur_kwh=(
                energy_price_tiers if price_type is PriceType.FIXED else {}
            ),
            spread_tiers_eur_kwh=spread_tiers,
            fixed_fee_eur_year=fixed_fee,
            per_kwh_extras_eur=extras,
            power_fee_eur_kw_year=power_fee,
            one_off_fee_eur=one_off,
            discounts=discounts,
            customer=CustomerType.DOMESTIC,
            residency=_residency(dettaglio),
            geo=_geo(el),
            losses_mode=policy.losses_mode(OfferSource.MLIBERO, price_type),
            dispatching_eur_kwh=dispatching_result.eur_kwh,
            dispatching_eur_year=dispatching_result.eur_year,
            dispatching_breakdown=dispatching_result.breakdown,
            dispatching_approximate=dispatching_result.approximate,
            consumption_min_kwh=consumo_min,
            consumption_max_kwh=consumo_max,
            valid_from=valid_from,
            valid_to=valid_to,
            duration_months=duration_months,
            duration_open_ended=duration_open_ended,
            supplier_vat=supplier_vat,
            supplier_name_source=supplier_name_source,
        )
    except ValueError as exc:
        return Excluded(offer_id, f"errore di validazione: {exc}")
    return offer


def iter_mlibero_offers(
    path: str,
    params: Parameters,
    operators: dict[str, Operator] | None = None,
    placet_names: dict[str, str] | None = None,
) -> Iterator[ParsedOffer]:
    """Stream-parse the mercato libero XML, clearing elements as it goes to
    keep memory bounded on the ~20 MB file.
    """
    context = ET.iterparse(path, events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event != "end" or _local(elem.tag) != "offerta":
            continue
        parsed = parse_offerta(
            elem, params, operators=operators, placet_names=placet_names
        )
        elem.clear()
        root.clear()
        yield parsed


def parse_mlibero_file(
    path: str,
    params: Parameters,
    operators: dict[str, Operator] | None = None,
    placet_names: dict[str, str] | None = None,
) -> list[ParsedOffer]:
    return list(iter_mlibero_offers(path, params, operators, placet_names))
