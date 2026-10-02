from datetime import date

import pytest

from bestbill.core.calculator import compare, estimate_annual_cost
from bestbill.core.models import (
    ConsumptionTier,
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


def test_offer_defaults():
    offer = Offer(
        id="legacy",
        supplier="Legacy",
        name="Legacy",
        source="placet",
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


# --- Consumption-tiered discounts (ARERA Sconto/PrezziSconto VALIDO_DA/
# VALIDO_FINO, docs/pricing-policy.md and the ATENA sample offer) ---


def test_tiered_discount_only_applies_below_valido_fino():
    """Regression test for the ATENA bug: a discount with VALIDO_DA/
    VALIDO_FINO must only apply to the kWh inside that band, not the
    customer's whole annual consumption.
    """
    profile = make_profile([225.0] * 12)  # 2700 kWh/year
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Sconto 40% sui primi 840 kWh/a",
        validity=DiscountValidity.WITHIN_12_MONTHS,
        conditional=False,
        amount=0.075680,
        unit=DiscountUnit.EUR_KWH,
        consumption_from_kwh=0.0,
        consumption_to_kwh=840.0,
    )
    offer = fixed_offer(
        price=0.1774,
        spread=0.0,
        fee=99.0,
        dispatching_eur_kwh=0.024,
        discounts=[discount],
    )

    comparison = compare([offer], profile, pun)

    expected = 0.1774 * 2700 + 99 + 0.024 * 2700 - 0.075680 * 840
    assert comparison.results[0].cost_eur == pytest.approx(expected, abs=1e-6)
    assert comparison.results[0].cost_eur == pytest.approx(579.21, abs=0.01)
    # The old (buggy) behaviour subtracted 0.075680 * 2700 = 204.34, giving
    # a materially lower (wrong) cost -- guard against regressing to it.
    wrong_cost = 0.1774 * 2700 + 99 + 0.024 * 2700 - 0.075680 * 2700
    assert comparison.results[0].cost_eur != pytest.approx(wrong_cost, abs=1.0)


@pytest.mark.parametrize(
    ("total_kwh", "expected_discount"),
    [
        (500.0, 0.075680 * 500.0),  # entirely below VALIDO_FINO
        (840.0, 0.075680 * 840.0),  # exactly at VALIDO_FINO
        (2700.0, 0.075680 * 840.0),  # above VALIDO_FINO: capped at the band
    ],
)
def test_tiered_discount_boundary_cases(total_kwh, expected_discount):
    monthly = total_kwh / 12.0
    profile = make_profile([monthly] * 12)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Sconto a scaglione",
        validity=DiscountValidity.WITHIN_12_MONTHS,
        conditional=False,
        amount=0.075680,
        unit=DiscountUnit.EUR_KWH,
        consumption_from_kwh=0.0,
        consumption_to_kwh=840.0,
    )
    offer = fixed_offer(price=0.10, spread=0.0, fee=0.0, discounts=[discount])

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].breakdown.discounts == pytest.approx(
        expected_discount, abs=1e-6
    )


def test_multiple_discount_tiers_are_additive_over_their_ranges():
    """Multiple PrezziSconto tiers on the same Sconto (e.g. 0-1000,
    1001-1500, 1501-3000) become separate ``Discount`` objects and must
    add up marginally (docs/pricing-policy.md).
    """
    profile = make_profile([250.0] * 12)  # 3000 kWh/year
    pun = make_pun([0.10] * 12)
    tiers = [
        Discount(
            name="tier1",
            validity=DiscountValidity.WITHIN_12_MONTHS,
            conditional=False,
            amount=0.265,
            unit=DiscountUnit.EUR_KWH,
            consumption_from_kwh=0.0,
            consumption_to_kwh=1000.0,
        ),
        Discount(
            name="tier2",
            validity=DiscountValidity.WITHIN_12_MONTHS,
            conditional=False,
            amount=0.173,
            unit=DiscountUnit.EUR_KWH,
            consumption_from_kwh=1001.0,
            consumption_to_kwh=1500.0,
        ),
        Discount(
            name="tier3",
            validity=DiscountValidity.WITHIN_12_MONTHS,
            conditional=False,
            amount=0.1798,
            unit=DiscountUnit.EUR_KWH,
            consumption_from_kwh=1501.0,
            consumption_to_kwh=3000.0,
        ),
    ]
    offer = fixed_offer(price=0.20, spread=0.0, fee=0.0, discounts=tiers)

    comparison = compare([offer], profile, pun)

    expected_discount = 0.265 * 1000 + 0.173 * 499 + 0.1798 * 1499
    assert comparison.results[0].breakdown.discounts == pytest.approx(
        expected_discount, abs=1e-6
    )


def test_duration_months_prorates_discount_to_first_n_months():
    """ARERA Sconto/PeriodoValidita/DURATA: a discount valid for the first
    N months only applies to the kWh consumed in those months.
    """
    profile = make_profile([100.0, 200.0] + [50.0] * 10)
    pun = make_pun([0.10] * 12)
    discount = Discount(
        name="Sconto primo mese",
        validity=DiscountValidity.WITHIN_12_MONTHS,
        conditional=False,
        amount=0.175,
        unit=DiscountUnit.EUR_KWH,
        duration_months=1,
    )
    offer = fixed_offer(price=0.20, spread=0.0, fee=0.0, discounts=[discount])

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].breakdown.discounts == pytest.approx(
        0.175 * 100.0, abs=1e-6
    )


# --- Consumption-tiered component prices (ARERA IntervalloPrezzi
# CONSUMO_DA/CONSUMO_A) ---


def test_tiered_energy_price_is_marginal_per_band():
    profile = make_profile([100.0] * 12)  # 1200 kWh/year
    pun = make_pun([0.10] * 12)
    tiers = [
        ConsumptionTier(from_kwh=0.0, to_kwh=1000.0, price_eur_kwh=0.10),
        ConsumptionTier(from_kwh=1000.0, to_kwh=None, price_eur_kwh=0.15),
    ]
    offer = fixed_offer(
        price=0.0,
        spread=0.0,
        fee=0.0,
        energy_price_tiers_eur_kwh={"mono": tiers},
    )

    comparison = compare([offer], profile, pun)

    expected = 1000 * 0.10 + 200 * 0.15
    assert comparison.results[0].cost_eur == pytest.approx(expected, abs=1e-6)


def test_tiered_energy_price_below_first_tier_upper_bound():
    profile = make_profile([50.0] * 12)  # 600 kWh/year, entirely in tier 1
    pun = make_pun([0.10] * 12)
    tiers = [
        ConsumptionTier(from_kwh=0.0, to_kwh=1000.0, price_eur_kwh=0.10),
        ConsumptionTier(from_kwh=1000.0, to_kwh=None, price_eur_kwh=0.15),
    ]
    offer = fixed_offer(
        price=0.0,
        spread=0.0,
        fee=0.0,
        energy_price_tiers_eur_kwh={"mono": tiers},
    )

    comparison = compare([offer], profile, pun)

    assert comparison.results[0].cost_eur == pytest.approx(600 * 0.10, abs=1e-6)


def test_tiered_price_layers_on_top_of_flat_price():
    """A flat base price plus a tiered surcharge above a threshold (the
    000670* sample offers) must add up, not overwrite each other.
    """
    profile = make_profile([250.0] * 12)  # 3000 kWh/year
    pun = make_pun([0.10] * 12)
    tiers = [ConsumptionTier(from_kwh=2500.0, to_kwh=None, price_eur_kwh=0.0275)]
    offer = variable_offer(
        spread=0.0,
        fee=0.0,
        spread_tiers_eur_kwh={"mono": tiers},
    )

    comparison = compare([offer], profile, pun)

    expected_energy = 3000 * 0.10 + 500 * 0.0275
    assert comparison.results[0].breakdown.energy == pytest.approx(
        expected_energy, abs=1e-6
    )
