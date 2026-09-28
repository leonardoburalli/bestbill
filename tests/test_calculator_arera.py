from datetime import date

import pytest

from bestbill.core.calculator import compare, estimate_annual_cost
from bestbill.core.models import (
    CustomerType,
    Discount,
    DiscountUnit,
    DiscountValidity,
    GeoRestriction,
    LossesMode,
    Offer,
    Residency,
)

from .helpers import fixed_offer, make_profile, make_pun, variable_offer


def test_losses_index_only_multiplies_pun_not_spread():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = variable_offer(spread=0.02, fee=0.0, losses_mode=LossesMode.INDEX_ONLY)

    comparison = compare([offer], profile, pun)

    # pun * 1.10 + spread (spread untouched) -- mercato libero variable rule
    expected = 1200.0 * (0.10 * 1.10 + 0.02)
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_losses_index_and_spread_multiplies_both():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = variable_offer(
        spread=0.02, fee=0.0, losses_mode=LossesMode.INDEX_AND_SPREAD
    )

    comparison = compare([offer], profile, pun)

    # (pun + spread) * 1.10 -- PLACET variable rule (PINGM + alpha)
    expected = 1200.0 * (0.12 * 1.10)
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_fixed_offers_never_get_losses_even_if_mode_set():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    # Per the verified v4.0 rules, fixed offers get NO losses; the policy
    # module never sets a losses_mode other than NONE for fixed offers.
    # This test documents the engine's behaviour if it were: it always
    # respects the offer's own losses_mode (the "no losses on fixed"
    # decision lives in policy.losses_mode(), not the engine).
    offer = fixed_offer(price=0.15, spread=0.0, fee=0.0, losses_mode=LossesMode.NONE)

    comparison = compare([offer], profile, pun)

    expected = 1200.0 * 0.15
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_per_kwh_extras_not_multiplied_by_losses():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(
        price=0.10,
        spread=0.0,
        fee=0.0,
        losses_mode=LossesMode.INDEX_AND_SPREAD,
        per_kwh_extras_eur=0.02,
    )

    comparison = compare([offer], profile, pun)

    expected = 1200.0 * (0.10 * 1.10 + 0.02)
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_power_fee_priced_with_committed_power():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(price=0.10, spread=0.0, fee=0.0, power_fee_eur_kw_year=20.0)

    comparison = compare([offer], profile, pun, committed_power_kw=4.5)

    expected = 1200.0 * 0.10 + 20.0 * 4.5
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_one_off_fee_added_to_annual_cost():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(price=0.10, spread=0.0, fee=0.0, one_off_fee_eur=60.0)

    comparison = compare([offer], profile, pun)

    # docs/pricing-policy.md §5: MACROAREA 05/01 UM 05 one-off fees are
    # added to the 12-month total, not just shown for reference.
    assert comparison.results[0].cost_eur == pytest.approx(1200.0 * 0.10 + 60.0)
    assert comparison.results[0].one_off_fee_eur == 60.0
    assert comparison.results[0].breakdown.one_off == 60.0


def test_unconditional_discount_reduces_cost():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Bonus",
        validity=DiscountValidity.ON_ENTRY,
        conditional=False,
        amount=50.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    offer = fixed_offer(price=0.10, spread=0.0, fee=100.0, discounts=[discount])

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].cost_eur == pytest.approx(1200.0 * 0.10 + 100.0 - 50.0)


def test_conditional_discount_not_priced_but_shown():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Bonus SDD",
        validity=DiscountValidity.WITHIN_12_MONTHS,
        conditional=True,
        amount=21.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    offer = fixed_offer(price=0.10, spread=0.0, fee=100.0, discounts=[discount])

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].cost_eur == pytest.approx(1200.0 * 0.10 + 100.0)
    assert comparison.results[0].conditional_discounts == [discount]


def test_beyond_12_months_discount_not_priced():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Later",
        validity=DiscountValidity.BEYOND_12_MONTHS,
        conditional=False,
        amount=999.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    offer = fixed_offer(price=0.10, spread=0.0, fee=0.0, discounts=[discount])

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].cost_eur == pytest.approx(1200.0 * 0.10)


def test_non_domestic_offer_excluded():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(customer=CustomerType.NON_DOMESTIC)

    comparison = compare([offer], profile, pun)

    assert comparison.results == []
    assert comparison.excluded == [(offer.id, "offerta non domestica")]


def test_residents_only_offer_excluded_for_non_resident_user():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(residency=Residency.RESIDENTS)

    comparison = compare([offer], profile, pun, residency="non_resident")

    assert comparison.excluded == [(offer.id, "offerta riservata ai residenti")]


def test_residents_only_offer_included_for_resident_user():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(residency=Residency.RESIDENTS)

    comparison = compare([offer], profile, pun, residency="resident")

    assert len(comparison.results) == 1


def test_geo_restricted_offer_excluded_without_istat_comune():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(geo=GeoRestriction(comuni=frozenset({"001272"})))

    comparison = compare([offer], profile, pun, istat_comune=None)

    assert comparison.excluded == [(offer.id, "zona non specificata")]


def test_geo_restricted_offer_included_with_matching_comune():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(geo=GeoRestriction(comuni=frozenset({"001272"})))

    comparison = compare([offer], profile, pun, istat_comune="001272")

    assert len(comparison.results) == 1


def test_geo_restricted_offer_matches_via_provincia_prefix():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(geo=GeoRestriction(province=frozenset({"001"})))

    comparison = compare([offer], profile, pun, istat_comune="001272")

    assert len(comparison.results) == 1


def test_geo_restricted_offer_excluded_for_non_matching_comune():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(geo=GeoRestriction(comuni=frozenset({"001272"})))

    comparison = compare([offer], profile, pun, istat_comune="999999")

    assert comparison.excluded == [
        (offer.id, "offerta non disponibile nel comune indicato")
    ]


def test_estimate_annual_cost_ignores_eligibility():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(
        price=0.10,
        spread=0.0,
        fee=0.0,
        consumption_max_kwh=1.0,  # would normally exclude the offer
        valid_to=date(2000, 1, 1),  # expired
    )

    cost = estimate_annual_cost(offer, profile, pun)

    assert cost == pytest.approx(1200.0 * 0.10)


def test_estimate_annual_cost_none_when_variable_and_no_pun():
    profile = make_profile([100.0] * 12)
    empty_pun = make_pun([])
    offer = variable_offer()

    assert estimate_annual_cost(offer, profile, empty_pun) is None


def test_custom_offer_defaults_keep_legacy_behaviour():
    offer = Offer(
        id="legacy",
        supplier="Legacy",
        name="Legacy",
        source="custom",
        price_type="fixed",
        band_structure="mono",
        energy_price_eur_kwh={"mono": 0.10},
        spread_eur_kwh={"mono": 0.0},
        fixed_fee_eur_year=0.0,
    )
    assert offer.customer.value == "domestic"
    assert offer.residency.value == "any"
    assert offer.geo is None
    assert offer.losses_mode.value == "none"
    assert offer.discounts == []


def test_breakdown_parts_sum_to_cost_eur_fixed_offer_with_everything():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Bonus",
        validity=DiscountValidity.ON_ENTRY,
        conditional=False,
        amount=30.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    offer = fixed_offer(
        price=0.12,
        spread=0.0,
        fee=90.0,
        per_kwh_extras_eur=0.01,
        power_fee_eur_kw_year=15.0,
        one_off_fee_eur=25.0,
        dispatching_eur_kwh=0.02,
        dispatching_eur_year=1.107,
        discounts=[discount],
    )

    comparison = compare([offer], profile, pun, committed_power_kw=3.0)
    result = comparison.results[0]
    b = result.breakdown

    assert (
        b.energy
        + b.fixed_fees
        + b.per_kwh_extras
        + b.power_fee
        + b.dispatching
        + b.one_off
        - b.discounts
        == pytest.approx(b.total)
    )
    assert b.total == pytest.approx(result.cost_eur)
    assert b.energy == pytest.approx(1200.0 * 0.12)
    assert b.fixed_fees == pytest.approx(90.0 + 1.107)
    assert b.per_kwh_extras == pytest.approx(1200.0 * 0.01)
    assert b.power_fee == pytest.approx(15.0 * 3.0)
    assert b.dispatching == pytest.approx(1200.0 * 0.02)
    assert b.one_off == pytest.approx(25.0)
    assert b.discounts == pytest.approx(30.0)


def test_break_even_pun_correct_with_dispatching_discounts_and_one_off():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    fixed = fixed_offer(offer_id="fixed", price=0.15, spread=0.0, fee=50.0)
    discount = Discount(
        name="Bonus",
        validity=DiscountValidity.ON_ENTRY,
        conditional=False,
        amount=20.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    var = variable_offer(
        offer_id="var",
        spread=0.03,
        fee=20.0,
        dispatching_eur_kwh=0.024,
        dispatching_eur_year=1.107,
        one_off_fee_eur=10.0,
        discounts=[discount],
    )

    comparison = compare([fixed, var], profile, pun)
    var_result = next(r for r in comparison.results if r.offer_id == "var")
    break_even = var_result.break_even_pun_eur_kwh
    assert break_even is not None

    from bestbill.core.models import Flat as FlatScenario

    comparison_at_break_even = compare(
        [fixed, var], profile, pun, scenario=FlatScenario(value=break_even)
    )
    fixed_cost = next(
        r.cost_eur for r in comparison_at_break_even.results if r.offer_id == "fixed"
    )
    var_cost = next(
        r.cost_eur for r in comparison_at_break_even.results if r.offer_id == "var"
    )
    assert var_cost == pytest.approx(fixed_cost, abs=1e-6)
