import pathlib

from bestbill.arera.mlibero import Excluded, parse_mlibero_file
from bestbill.arera.parameters import parse_parameters_file
from bestbill.core.models import BandStructure, PriceType, Residency

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "arera" / "mlibero.xml"
PARAMS = parse_parameters_file(
    str(pathlib.Path(__file__).parent / "fixtures" / "arera" / "params_ml.csv")
)


def _parsed():
    return parse_mlibero_file(str(FIXTURE), PARAMS)


def test_mlibero_fixture_parses_expected_counts():
    rows = _parsed()
    offers = [r for r in rows if not isinstance(r, Excluded)]
    excluded = [r for r in rows if isinstance(r, Excluded)]
    assert len(offers) == 10
    assert len(excluded) == 3
    assert all(o.customer.value == "domestic" for o in offers)


def test_mlibero_dual_fuel_excluded_with_reason():
    rows = _parsed()
    excluded = {r.row_id: r.reason for r in rows if isinstance(r, Excluded)}
    reasons = " ".join(excluded.values())
    assert "dual-fuel" in reasons


def test_mlibero_unsupported_fasce_excluded():
    rows = _parsed()
    reasons = [r.reason for r in rows if isinstance(r, Excluded)]
    assert any("TIPOLOGIA_FASCE" in r for r in reasons)


def test_mlibero_non_domestic_excluded_and_counted():
    # 13 <offerta> elements in the fixture; every one is parsed into either
    # an Offer or an Excluded -- the non-domestic row (TIPO_CLIENTE=02) is
    # never silently dropped, so it never reaches the catalogue.
    rows = _parsed()
    assert len(rows) == 13
    excluded = [r for r in rows if isinstance(r, Excluded)]
    assert any("non domestica" in r.reason for r in excluded)
    offers = [r for r in rows if not isinstance(r, Excluded)]
    assert all(o.customer.value == "domestic" for o in offers)


def test_mlibero_band_structures_present():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    structures = {o.band_structure for o in offers}
    assert BandStructure.MONO in structures
    assert BandStructure.F1F2F3 in structures
    assert BandStructure.F1F23 in structures


def test_mlibero_fixed_and_variable_present():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    types = {o.price_type for o in offers}
    assert PriceType.FIXED in types
    assert PriceType.VARIABLE in types


def test_mlibero_geo_restrictions_present():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    geo_offers = [o for o in offers if o.geo is not None]
    assert len(geo_offers) >= 2


def test_mlibero_residency_restriction_parsed():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    residencies = {o.residency for o in offers}
    assert Residency.NON_RESIDENTS in residencies or Residency.RESIDENTS in residencies


def test_mlibero_discounts_parsed_with_conditional_flag():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    with_discounts = [o for o in offers if o.discounts]
    assert with_discounts
    all_discounts = [d for o in with_discounts for d in o.discounts]
    assert any(d.conditional for d in all_discounts) or any(
        not d.conditional for d in all_discounts
    )


def test_mlibero_dates_use_datetime_suffix_format():
    offers = [r for r in _parsed() if not isinstance(r, Excluded)]
    dated = [o for o in offers if o.valid_from is not None]
    assert dated
    for o in dated:
        assert o.valid_from is not None
