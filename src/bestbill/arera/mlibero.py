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
from bestbill.arera.parameters import Parameters
from bestbill.core.models import (
    BandStructure,
    CustomerType,
    Discount,
    GeoRestriction,
    Offer,
    OfferSource,
    PriceType,
    Residency,
)

_NS = "{http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01}"

#: Sconto/PrezziSconto/TIPOLOGIA code meaning "discount on Maggior Tutela".
_SCONTO_TIPOLOGIA_MAGGIOR_TUTELA = "04"


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


def _parse_componenti(
    el: ET.Element, price_type: PriceType, tipologia_fasce: str
) -> tuple[dict[str, float], dict[str, float], float, float, float, str | None]:
    """Returns (energy_price, spread, per_kwh_extras, fixed_fee, one_off,
    exclusion_reason).
    """
    energy_price: dict[str, float] = {}
    spread: dict[str, float] = {}
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
            unita = _text(interval, "UNITA_MISURA")
            prezzo = _to_float(_text(interval, "PREZZO"))
            if unita is None or prezzo is None:
                continue
            role, reason = policy.classify_component(macroarea, unita, price_type)
            if role is None:
                return {}, {}, 0.0, 0.0, 0.0, reason
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
                        0.0,
                        0.0,
                        0.0,
                        (
                            f"FASCIA_COMPONENTE {fascia!r} non mappabile per "
                            f"TIPOLOGIA_FASCE {tipologia_fasce!r}"
                        ),
                    )
                target = (
                    energy_price
                    if role == policy.ComponentRole.ENERGY_PRICE
                    else spread
                )
                target[band] = target.get(band, 0.0) + prezzo

    extras = sum(extras_values) / len(extras_values) if extras_values else 0.0
    return energy_price, spread, extras, fixed_fee, one_off, None


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
        iva_code = _text(sconto, "IVA_SCONTO")
        for prezzo_sconto in sconto.findall(f"{_NS}PrezziSconto"):
            tipologia = _text(prezzo_sconto, "TIPOLOGIA")
            if tipologia == _SCONTO_TIPOLOGIA_MAGGIOR_TUTELA:
                return [], policy.MAGGIOR_TUTELA_REASON
            unita = _text(prezzo_sconto, "UNITA_MISURA")
            prezzo = _to_float(_text(prezzo_sconto, "PREZZO"))
            if unita is None or prezzo is None:
                continue
            discounts.append(
                Discount(
                    name=name,
                    description=description,
                    validity=validity,
                    conditional=conditional,
                    amount=policy.discount_nominal_to_pre_vat(prezzo, iva_code),
                    unit=policy.unita_misura_to_discount_unit(unita),
                    applies_before_vat=True,
                )
            )
    return discounts, None


def _band_structure_from_tipologia(code: str) -> BandStructure:
    return {
        TipologiaFasce.MONO: BandStructure.MONO,
        TipologiaFasce.F1F2F3: BandStructure.F1F2F3,
        TipologiaFasce.F1F23: BandStructure.F1F23,
    }[TipologiaFasce(code)]


def parse_offerta(el: ET.Element, params: Parameters) -> ParsedOffer:
    """Parse one ``<offerta>`` element into an :class:`Excluded` (unsupported
    structure, non-domestic, or any other unpriceable case -- always
    counted, never silently dropped) or an :class:`Offer`.
    """
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
        idx_el = el.find(f"{_NS}RiferimentiPrezzoEnergia")
        idx_code = _text(idx_el, "IDX_PREZZO_ENERGIA") if idx_el is not None else None
        if idx_code is not None and policy.idx_is_maggior_tutela(idx_code):
            return Excluded(offer_id, policy.MAGGIOR_TUTELA_REASON)
        if idx_code is None or not policy.idx_is_supported(idx_code):
            return Excluded(
                offer_id, f"IDX_PREZZO_ENERGIA non supportato: {idx_code!r}"
            )

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

    energy_price, spread, extras, fixed_fee, one_off, reason = _parse_componenti(
        el, price_type, tipologia_fasce
    )
    if reason is not None:
        return Excluded(offer_id, reason)

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
    if price_type is PriceType.FIXED and set(energy_price) != expected_keys:
        return Excluded(
            offer_id,
            f"prezzi energia incompleti per {band_structure!r}: {sorted(energy_price)}",
        )
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

    contatti = dettaglio.find(f"{_NS}Contatti")
    url = None
    if contatti is not None:
        url = _text(contatti, "URL_OFFERTA") or _text(contatti, "URL_SITO_VENDITORE")

    try:
        piva = (
            (ident.findtext(f"{_NS}PIVA_UTENTE") or "").strip()
            if ident is not None
            else ""
        )
        offer = Offer(
            id=offer_id,
            supplier=f"P.IVA {piva}" if piva else "sconosciuto",
            name=_text(dettaglio, "NOME_OFFERTA") or offer_id,
            url=url,
            source=OfferSource.MLIBERO,
            price_type=price_type,
            band_structure=band_structure,
            energy_price_eur_kwh=energy_price if price_type is PriceType.FIXED else {},
            spread_eur_kwh=spread,
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
        )
    except ValueError as exc:
        return Excluded(offer_id, f"errore di validazione: {exc}")
    return offer


def iter_mlibero_offers(path: str, params: Parameters) -> Iterator[ParsedOffer]:
    """Stream-parse the mercato libero XML, clearing elements as it goes to
    keep memory bounded on the ~20 MB file.
    """
    context = ET.iterparse(path, events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event != "end" or _local(elem.tag) != "offerta":
            continue
        parsed = parse_offerta(elem, params)
        elem.clear()
        root.clear()
        yield parsed


def parse_mlibero_file(path: str, params: Parameters) -> list[ParsedOffer]:
    return list(iter_mlibero_offers(path, params))
