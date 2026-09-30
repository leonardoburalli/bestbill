import pathlib

from bestbill.arera.parameters import parse_parameters_file
from bestbill.arera.placet import Excluded, parse_placet_file
from bestbill.core.models import BandStructure, PriceType

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "arera" / "placet.csv"
PARAMS = parse_parameters_file(
    str(pathlib.Path(__file__).parent / "fixtures" / "arera" / "params_e.csv")
)


def test_placet_fixture_parses_only_domestic_rows():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = [r for r in rows if not isinstance(r, Excluded)]
    assert len(offers) == 17
    assert all(o.customer.value == "domestic" for o in offers)


def test_placet_fixed_f1f23_offer_fields():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = {r.id: r for r in rows if not isinstance(r, Excluded)}
    offer = offers["028269ESFMP01XXPLACLFISDOM260812"]
    assert offer.price_type is PriceType.FIXED
    assert offer.band_structure is BandStructure.F1F23
    assert offer.energy_price_eur_kwh == {"F1": 0.385, "F23": 0.385}
    assert offer.fixed_fee_eur_year == 300.0
    assert offer.losses_mode.value == "none"


def test_placet_variable_offer_without_p_vol_defaults_to_mono_spread():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = {r.id: r for r in rows if not isinstance(r, Excluded)}
    offer = offers["028269ESVMP01XXPLACLVARDOM260812"]
    assert offer.price_type is PriceType.VARIABLE
    assert offer.band_structure is BandStructure.MONO
    assert offer.energy_price_eur_kwh == {}
    assert offer.spread_eur_kwh == {"mono": 0.045}
    assert offer.fixed_fee_eur_year == 300.0
    # PLACET variable offers apply losses to (PINGM + alpha) together.
    assert offer.losses_mode.value == "index_and_spread"


def test_placet_geo_restricted_offer_has_geo():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = {r.id: r for r in rows if not isinstance(r, Excluded)}
    geo_offer = next(o for o in offers.values() if o.geo is not None)
    assert geo_offer.geo.comuni or geo_offer.geo.province or geo_offer.geo.regioni


def test_placet_dates_parsed():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = {r.id: r for r in rows if not isinstance(r, Excluded)}
    offer = offers["028269ESFMP01XXPLACLFISDOM260812"]
    assert offer.valid_from is not None
    assert offer.valid_to is not None
    assert offer.valid_from < offer.valid_to


_HEADER = (
    "denominazione,codice_fiscale,p_iva,url_sito_venditore,telefono,nome_offerta,"
    "cod_offerta,url_offerta,modalita_attivazione,modalita_pagamento,data_inizio,"
    "data_fine,tipo_cliente,tipo_offerta,p_fix_f,p_fix_v,p_vol_f1,p_vol_f2,p_vol_f3,"
    "p_vol_bf1,p_vol_bf23,p_vol_mono,alpha,regione,provincia,comune\n"
)


def _rows(csv_text: str):
    from bestbill.arera.placet import parse_placet_rows

    return list(parse_placet_rows(_HEADER + csv_text, PARAMS))


def test_placet_unsupported_tipo_offerta_excluded():
    row = "Alfa,,,,,Nome,ID1,,,,,,domestico,prezzo indicizzato,,,,,,,,,,,,,\n"
    result = _rows(row)
    assert len(result) == 1
    assert isinstance(result[0], Excluded)
    assert "tipo_offerta non supportato" in result[0].reason


def test_placet_fixed_offer_with_no_price_excluded():
    row = "Alfa,,,,,Nome,ID2,,,,,,domestico,prezzo fisso,300,,,,,,,,,,,\n"
    result = _rows(row)
    assert len(result) == 1
    assert isinstance(result[0], Excluded)
    assert "nessun prezzo" in result[0].reason


def test_placet_missing_fee_excluded():
    row = "Alfa,,,,,Nome,ID3,,,,,,domestico,prezzo fisso,,,,,,0.1,0.1,0.1,,,,\n"
    result = _rows(row)
    assert len(result) == 1
    assert isinstance(result[0], Excluded)
    assert "canone annuo" in result[0].reason


def test_placet_non_domestic_row_excluded_and_counted():
    row = "Alfa,,,,,Nome,ID4,,,,,,non domestico,prezzo fisso,300,,,,,,,0.1,,,,\n"
    result = _rows(row)
    assert len(result) == 1
    assert isinstance(result[0], Excluded)
    assert "non domestica" in result[0].reason


def test_placet_invalid_offer_validation_error_excluded():
    # Negative fee triggers Offer's own ge=0 validation.
    row = "Alfa,,,,,Nome,ID5,,,,,,domestico,prezzo fisso,-5,,,,,,,0.1,,,,\n"
    result = _rows(row)
    assert len(result) == 1
    assert isinstance(result[0], Excluded)
    assert "errore di validazione" in result[0].reason


def test_placet_decode_falls_back_to_cp1252():
    from bestbill.arera.placet import parse_placet_bytes

    raw = (
        _HEADER
        + "Alfa città,,,,,Nome,ID6,,,,,,domestico,prezzo fisso,300,,,,,,,0.1,,,,\n"
    ).encode("cp1252")
    result = list(parse_placet_bytes(raw, PARAMS))
    assert len(result) == 1
    assert not isinstance(result[0], Excluded)


def test_placet_duration_is_12_months():
    rows = parse_placet_file(str(FIXTURE), PARAMS)
    offers = [r for r in rows if not isinstance(r, Excluded)]
    assert offers
    assert all(o.duration_months == 12 and not o.duration_open_ended for o in offers)
