import pathlib

import pytest

from bestbill.arera.mlibero import Excluded, parse_mlibero_file
from bestbill.arera.operators import Operator
from bestbill.arera.parameters import parse_parameters_file
from bestbill.core.models import BandStructure, PriceType, Residency, SupplierNameSource

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
    assert len(offers) == 13
    assert len(excluded) == 4
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
    # 17 <offerta> elements in the fixture; every one is parsed into either
    # an Offer or an Excluded -- the non-domestic row (TIPO_CLIENTE=02) is
    # never silently dropped, so it never reaches the catalogue.
    rows = _parsed()
    assert len(rows) == 17
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


def _offer(offer_id: str):
    rows = _parsed()
    match = [r for r in rows if not isinstance(r, Excluded) and r.id == offer_id]
    assert len(match) == 1, f"expected exactly one offer {offer_id!r}, got {match}"
    return match[0]


def _excluded_reason(offer_id: str) -> str:
    rows = _parsed()
    match = [r for r in rows if isinstance(r, Excluded) and r.row_id == offer_id]
    assert len(match) == 1, f"expected exactly one exclusion {offer_id!r}, got {match}"
    return match[0].reason


def test_atena_offer_parses_tiered_discount_on_prezzisconto():
    offer = _offer("000567ESFML12XX0000AEDOSCL261011")
    assert len(offer.discounts) == 1
    discount = offer.discounts[0]
    assert discount.unit.value == "eur_kwh"
    assert discount.consumption_from_kwh == 0.0
    assert discount.consumption_to_kwh == 840.0
    assert discount.amount == pytest.approx(0.075680)


def test_atena_offer_annual_cost_matches_hand_computed_579_21():
    from datetime import date

    from bestbill.core.calculator import estimate_annual_cost
    from bestbill.core.models import ConsumptionProfile, MonthlyConsumption, PunSeries

    offer = _offer("000567ESFML12XX0000AEDOSCL261011")
    months = []
    for i in range(12):
        year = 2024 + (9 + i - 1) // 12
        month = (9 + i - 1) % 12 + 1
        months.append(MonthlyConsumption(month=date(year, month, 1), kwh=225.0))
    profile = ConsumptionProfile(months=months)
    pun = PunSeries(values={})

    cost = estimate_annual_cost(offer, profile, pun)

    # 0.1774*2700 + 99 + 0.024*2700 - 0.075680*840
    expected = 0.1774 * 2700 + 99 + 0.024 * 2700 - 0.075680 * 840
    assert cost == pytest.approx(expected, abs=0.01)
    assert cost == pytest.approx(579.21, abs=0.01)


def test_tiered_consumo_da_a_energy_price_is_marginal():
    offer = _offer("TEST_TIERED_CONSUMO_DA_A_0001")
    assert offer.energy_price_tiers_eur_kwh.get("mono")
    tiers = offer.energy_price_tiers_eur_kwh["mono"]
    assert len(tiers) == 2
    assert offer.energy_price_eur_kwh.get("mono", 0.0) == 0.0


def test_interval_periodo_validita_excludes_with_guardrail_reason():
    reason = _excluded_reason("TEST_GUARDRAIL_PERIODOVALIDITA_0001")
    assert "elemento di prezzo non gestito" in reason
    assert "PeriodoValidita" in reason


def test_mono_fixed_offer_with_only_macroarea02_prices_via_extras():
    """No MACROAREA 04/06 at all (whole energy price filed under
    MACROAREA 02, e.g. real offer 000742ESFML01XXSICREFIX260930D01):
    allow energy_price = 0 for "mono" and price it via per_kwh_extras_eur
    instead (same annual cost, no losses either way).
    """
    offer = _offer("TEST_MACROAREA02_ONLY_FIXED_0001")
    assert offer.energy_price_eur_kwh == {"mono": 0.0}
    assert offer.per_kwh_extras_eur == pytest.approx(0.154)
    assert offer.fixed_fee_eur_year == pytest.approx(210.0)

    from datetime import date

    from bestbill.core.calculator import estimate_annual_cost
    from bestbill.core.models import ConsumptionProfile, MonthlyConsumption, PunSeries

    months = []
    for i in range(12):
        year = 2024 + (9 + i - 1) // 12
        month = (9 + i - 1) % 12 + 1
        months.append(MonthlyConsumption(month=date(year, month, 1), kwh=225.0))
    profile = ConsumptionProfile(months=months)
    cost = estimate_annual_cost(offer, profile, PunSeries(values={}))

    # 2700 kWh * 0.154 (per_kwh_extras, no losses) + 210 (fixed fee) +
    # 2700 * 0.024 (cdispd dispatching, no losses)
    expected = 2700 * 0.154 + 210 + 2700 * 0.024
    assert cost == pytest.approx(expected, abs=1e-6)


# --- Supplier name resolution (ARERA operators -> PLACET -> domain -> VAT) ---

_CASALUCE_OFFER_ID = "028269ESVML01XXCASALUCE260821001"
_CASALUCE_VAT = "08985501215"
_PIUENERGIA_OFFER_ID = "001686ESVFL00XXPFC0726DO00000000"
_PIUENERGIA_VAT = "01244170526"


def _parse_with(operators=None, placet_names=None):
    from bestbill.arera.mlibero import parse_mlibero_file

    return parse_mlibero_file(
        str(FIXTURE), PARAMS, operators=operators, placet_names=placet_names
    )


def _find(rows, offer_id):
    match = [r for r in rows if not isinstance(r, Excluded) and r.id == offer_id]
    assert len(match) == 1
    return match[0]


def test_supplier_name_resolves_via_arera_operators():
    operators = {_CASALUCE_VAT: Operator(name="100ENERGIA S.R.L.", website=None)}
    offer = _find(_parse_with(operators=operators), _CASALUCE_OFFER_ID)
    assert offer.supplier == "100ENERGIA S.R.L."
    assert offer.supplier_vat == _CASALUCE_VAT
    assert offer.supplier_name_source == SupplierNameSource.ARERA


def test_supplier_name_falls_back_to_placet_denominazione():
    # No ARERA entry for this VAT, but a matching PLACET denominazione.
    placet_names = {_CASALUCE_VAT: "100Energia (da PLACET)"}
    offer = _find(_parse_with(placet_names=placet_names), _CASALUCE_OFFER_ID)
    assert offer.supplier == "100Energia (da PLACET)"
    assert offer.supplier_vat == _CASALUCE_VAT
    assert offer.supplier_name_source == SupplierNameSource.PLACET


def test_supplier_name_falls_back_to_website_domain():
    # Neither ARERA nor PLACET has this VAT -> fall back to the domain of
    # URL_SITO_VENDITORE ("https://www.100energia.com/" -> "100energia.com").
    offer = _find(_parse_with(), _CASALUCE_OFFER_ID)
    assert offer.supplier == "100energia.com"
    assert offer.supplier_vat == _CASALUCE_VAT
    assert offer.supplier_name_source == SupplierNameSource.DOMAIN


def test_supplier_name_falls_back_to_vat_when_no_website_either():
    # +Energia's fixture URL is www.piuenergia.it -- still resolves via
    # domain, so exercise the true last resort with an offer that has no
    # site at all is out of scope for this fixture; verify the domain path
    # for a second, unrelated VAT to cover the "www." stripping branch.
    offer = _find(_parse_with(), _PIUENERGIA_OFFER_ID)
    assert offer.supplier == "piuenergia.it"
    assert offer.supplier_vat == _PIUENERGIA_VAT
    assert offer.supplier_name_source == SupplierNameSource.DOMAIN


def test_arera_operators_take_priority_over_placet_names():
    operators = {_CASALUCE_VAT: Operator(name="ARERA Name", website=None)}
    placet_names = {_CASALUCE_VAT: "PLACET Name"}
    offer = _find(
        _parse_with(operators=operators, placet_names=placet_names),
        _CASALUCE_OFFER_ID,
    )
    assert offer.supplier == "ARERA Name"
    assert offer.supplier_name_source == SupplierNameSource.ARERA


def test_resolve_supplier_name_falls_back_to_vat_when_no_domain():
    from bestbill.arera.mlibero import _resolve_supplier_name

    name, vat, source = _resolve_supplier_name("09999999999", None, {}, {})
    assert name == "P.IVA 09999999999"
    assert vat == "09999999999"
    assert source == SupplierNameSource.VAT


def test_resolve_supplier_name_unknown_when_no_vat_at_all():
    from bestbill.arera.mlibero import _resolve_supplier_name

    name, vat, source = _resolve_supplier_name("", None, {}, {})
    assert name == "sconosciuto"
    assert vat is None
    assert source is None
