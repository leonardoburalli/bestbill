"""PLACET EE CSV -> Offer.

See docs/arera-data.md "PLACET CSV" for the column reference. This
importer only prices domestic offers (``tipo_cliente == "domestico"``);
non-domestic rows are excluded and counted, like any other unsupported
structure, so the catalogue never contains a business offer.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime

from bestbill.arera import policy
from bestbill.arera.operators import zero_pad_vat
from bestbill.arera.parameters import Parameters
from bestbill.core.models import (
    BandStructure,
    CustomerType,
    GeoRestriction,
    Offer,
    OfferSource,
    PriceType,
    Residency,
    SupplierNameSource,
)

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class PlacetFormatError(ValueError):
    """The PLACET CSV doesn't match the expected format."""


@dataclass(frozen=True)
class Excluded:
    row_id: str
    reason: str


ParsedRow = Offer | Excluded


def _decode(raw: bytes) -> str:
    for encoding in _ENCODINGS_TO_TRY:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PlacetFormatError("could not decode PLACET CSV with any known encoding")


def _to_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value)


def _to_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value, "%d/%m/%Y").date()


def _geo_set(value: str) -> frozenset[str]:
    value = value.strip()
    if not value:
        return frozenset()
    return frozenset(code.strip() for code in value.split(";") if code.strip())


def _geo(row: dict[str, str]) -> GeoRestriction | None:
    regioni = _geo_set(row.get("regione", ""))
    province = _geo_set(row.get("provincia", ""))
    comuni = _geo_set(row.get("comune", ""))
    if not regioni and not province and not comuni:
        return None
    return GeoRestriction(regioni=regioni, province=province, comuni=comuni)


def parse_placet_rows(text: str, params: Parameters) -> Iterator[ParsedRow]:
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        offer_id = row.get("cod_offerta", "").strip() or row.get("nome_offerta", "?")
        tipo_cliente = row.get("tipo_cliente", "").strip()
        if tipo_cliente != "domestico":
            yield Excluded(
                offer_id, f"offerta non domestica (tipo_cliente={tipo_cliente!r})"
            )
            continue

        tipo_offerta = row.get("tipo_offerta", "").strip()
        if tipo_offerta == "prezzo fisso":
            price_type = PriceType.FIXED
        elif tipo_offerta == "prezzo variabile":
            price_type = PriceType.VARIABLE
        else:
            yield Excluded(offer_id, f"tipo_offerta non supportato: {tipo_offerta!r}")
            continue

        dispatching_result, disp_reason = policy.placet_domestic_dispatching(params)
        if dispatching_result is None:
            assert disp_reason is not None
            yield Excluded(offer_id, disp_reason)
            continue

        p_vol_bf1 = _to_float(row.get("p_vol_bf1", ""))
        p_vol_bf23 = _to_float(row.get("p_vol_bf23", ""))
        p_vol_mono = _to_float(row.get("p_vol_mono", ""))
        alpha = _to_float(row.get("alpha", ""))

        if p_vol_bf1 is not None and p_vol_bf23 is not None:
            band_structure = BandStructure.F1F23
            price_keys = {"F1": p_vol_bf1, "F23": p_vol_bf23}
        elif p_vol_mono is not None:
            band_structure = BandStructure.MONO
            price_keys = {"mono": p_vol_mono}
        elif price_type is PriceType.VARIABLE and alpha is not None:
            # Purely index-based domestic variable offers have no per-band
            # €/kWh price, only a spread (alpha) over PINGM.
            band_structure = BandStructure.MONO
            price_keys = {"mono": 0.0}
        else:
            yield Excluded(offer_id, "nessun prezzo €/kWh domestico riconosciuto")
            continue

        spread_keys = dict.fromkeys(price_keys, alpha or 0.0)

        fee = _to_float(
            row.get("p_fix_f" if price_type is PriceType.FIXED else "p_fix_v", "")
        )
        if fee is None:
            yield Excluded(offer_id, "canone annuo (p_fix_f/p_fix_v) mancante")
            continue

        energy_price = price_keys if price_type is PriceType.FIXED else {}

        raw_p_iva = row.get("p_iva", "").strip()
        supplier_vat = zero_pad_vat(raw_p_iva) if raw_p_iva else None

        try:
            offer = Offer(
                id=offer_id,
                supplier=row.get("denominazione", "").strip(),
                name=row.get("nome_offerta", "").strip(),
                url=row.get("url_offerta", "").strip() or None,
                source=OfferSource.PLACET,
                price_type=price_type,
                band_structure=band_structure,
                energy_price_eur_kwh=energy_price,
                spread_eur_kwh=spread_keys,
                fixed_fee_eur_year=fee,
                customer=CustomerType.DOMESTIC,
                residency=Residency.ANY,
                geo=_geo(row),
                losses_mode=policy.losses_mode(OfferSource.PLACET, price_type),
                dispatching_eur_kwh=dispatching_result.eur_kwh,
                dispatching_eur_year=dispatching_result.eur_year,
                dispatching_breakdown=dispatching_result.breakdown,
                dispatching_approximate=dispatching_result.approximate,
                valid_from=_to_date(row.get("data_inizio", "")),
                valid_to=_to_date(row.get("data_fine", "")),
                duration_months=policy.PLACET_DURATION_MONTHS,
                supplier_vat=supplier_vat,
                supplier_name_source=SupplierNameSource.PLACET,
            )
        except ValueError as exc:
            yield Excluded(offer_id, f"errore di validazione: {exc}")
            continue
        yield offer


def parse_placet_bytes(raw: bytes, params: Parameters) -> Iterator[ParsedRow]:
    yield from parse_placet_rows(_decode(raw), params)


def parse_placet_file(path: str, params: Parameters) -> list[ParsedRow]:
    with open(path, "rb") as f:
        raw = f.read()
    return list(parse_placet_bytes(raw, params))
