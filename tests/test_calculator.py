from datetime import date

import pytest

from bestbill.core.calculator import compare
from bestbill.core.models import Flat, Scaled

from .helpers import fixed_offer, make_profile, make_pun, month, variable_offer


def test_fixed_offer_cost_matches_manual_calculation():
    # 12 months summing to 3700 kWh (as the old test_tariffe.py fixture),
    # spread across the year.
    kwh_list = [300.0] * 11 + [400.0]
    profile = make_profile(kwh_list)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(price=0.03, spread=0.08, fee=100.0)

    comparison = compare([offer], profile, pun)

    # Expected: 3700 * (0.03 + 0.08) + 100 = 507.0
    assert comparison.results[0].cost_eur == pytest.approx(507.0)
    assert profile.total_kwh == 3700.0


def test_variable_offer_uses_aligned_pun_per_month():
    kwh_list = [100.0] * 12
    profile = make_profile(kwh_list)
    # PUN varies by month; aligned month-by-month with consumption.
    pun_values = [
        0.10,
        0.11,
        0.12,
        0.10,
        0.11,
        0.12,
        0.10,
        0.11,
        0.12,
        0.10,
        0.11,
        0.12,
    ]
    pun = make_pun(pun_values)
    offer = variable_offer(spread=0.02, fee=50.0)

    comparison = compare([offer], profile, pun)

    expected = sum(100.0 * (p + 0.02) for p in pun_values) + 50.0
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_substituted_pun_month_is_flagged_and_uses_latest_published():
    kwh_list = [100.0] * 12
    profile = make_profile(kwh_list)
    # Only the first 10 months are published; the last 2 consumption months
    # must fall back to the latest published PUN.
    pun = make_pun([0.10] * 10, start=(2024, 9))
    offer = variable_offer(spread=0.0, fee=0.0)

    comparison = compare([offer], profile, pun)

    assert comparison.assumptions.substituted_pun_months == [
        month(2025, 7),
        month(2025, 8),
    ]
    # Every substituted month falls back to the latest published value (0.10)
    assert comparison.assumptions.pun_months_used[month(2025, 7)] == 0.10
    assert comparison.assumptions.pun_months_used[month(2025, 8)] == 0.10


def test_variable_offer_excluded_when_no_pun_data_at_all():
    profile = make_profile([100.0] * 12)
    empty_pun = make_pun([])
    offer = variable_offer()

    comparison = compare([offer], profile, empty_pun)

    assert comparison.results == []
    assert comparison.excluded == [
        (offer.id, "PUN non disponibile per il periodo richiesto")
    ]


def test_scaled_scenario_multiplies_pun():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = variable_offer(spread=0.0, fee=0.0)

    comparison = compare([offer], profile, pun, scenario=Scaled(factor=1.2))

    assert comparison.results[0].cost_eur == pytest.approx(100.0 * 12 * 0.12)
    assert all(
        v == pytest.approx(0.12)
        for v in comparison.assumptions.pun_months_used.values()
    )


def test_flat_scenario_replaces_pun():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.05, 0.30] * 6)  # irrelevant, replaced by flat value
    offer = variable_offer(spread=0.0, fee=0.0)

    comparison = compare([offer], profile, pun, scenario=Flat(value=0.15))

    assert comparison.results[0].cost_eur == pytest.approx(100.0 * 12 * 0.15)
    assert all(v == 0.15 for v in comparison.assumptions.pun_months_used.values())


def test_user_bands_are_used_for_f1f2f3_offer():
    bands_list = [{"F1": 40.0, "F2": 30.0, "F3": 30.0}] * 12
    profile = make_profile([100.0] * 12, bands_list=bands_list)
    pun = make_pun([0.10] * 12)
    from bestbill.core.models import Offer

    offer = Offer(
        id="f123",
        supplier="Alfa",
        name="Alfa F123",
        source="custom",
        price_type="fixed",
        band_structure="f1f2f3",
        energy_price_eur_kwh={"F1": 0.20, "F2": 0.10, "F3": 0.05},
        spread_eur_kwh={"F1": 0.0, "F2": 0.0, "F3": 0.0},
        fixed_fee_eur_year=0.0,
    )

    comparison = compare([offer], profile, pun)

    expected = 12 * (40.0 * 0.20 + 30.0 * 0.10 + 30.0 * 0.05)
    assert comparison.results[0].cost_eur == pytest.approx(expected)
    assert comparison.assumptions.band_split_source == "user"


def test_default_split_used_when_no_user_bands():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(price=0.10, spread=0.0, fee=0.0)
    comparison = compare([offer], profile, pun)
    assert comparison.assumptions.band_split_source == "standard"


def test_f1f23_aggregation_combines_f2_and_f3():
    bands_list = [{"F1": 40.0, "F2": 30.0, "F3": 30.0}] * 12
    profile = make_profile([100.0] * 12, bands_list=bands_list)
    pun = make_pun([0.10] * 12)
    from bestbill.core.models import Offer

    offer = Offer(
        id="f123",
        supplier="Alfa",
        name="Alfa F123",
        source="custom",
        price_type="fixed",
        band_structure="f1f23",
        energy_price_eur_kwh={"F1": 0.20, "F23": 0.05},
        spread_eur_kwh={"F1": 0.0, "F23": 0.0},
        fixed_fee_eur_year=0.0,
    )

    comparison = compare([offer], profile, pun)

    expected = 12 * (40.0 * 0.20 + 60.0 * 0.05)
    assert comparison.results[0].cost_eur == pytest.approx(expected)


def test_offer_excluded_when_invalid_today():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    expired = fixed_offer(offer_id="expired", valid_to=date(2020, 1, 1))
    ok = fixed_offer(offer_id="ok", supplier="Beta", name="Beta")

    comparison = compare([expired, ok], profile, pun, today=date(2025, 1, 1))

    assert [r.offer_id for r in comparison.results] == ["ok"]
    assert comparison.excluded == [
        ("expired", "offerta scaduta (valid_to nel passato)")
    ]


def test_offer_excluded_when_consumption_out_of_range():
    profile = make_profile([100.0] * 12)  # 1200 kWh/year
    pun = make_pun([0.10] * 12)
    too_small_max = fixed_offer(offer_id="cap", consumption_max_kwh=500)
    ok = fixed_offer(offer_id="ok", supplier="Beta", name="Beta")

    comparison = compare([too_small_max, ok], profile, pun)

    assert [r.offer_id for r in comparison.results] == ["ok"]
    assert comparison.excluded == [
        ("cap", "consumo annuo sopra la soglia massima dell'offerta")
    ]


def test_sorting_by_cost_then_supplier_then_name_ties():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    # Same cost for all three; ties broken by supplier then name.
    a = fixed_offer(
        offer_id="a", supplier="Zeta", name="Z", price=0.10, spread=0.0, fee=0.0
    )
    b = fixed_offer(
        offer_id="b", supplier="Alfa", name="B", price=0.10, spread=0.0, fee=0.0
    )
    c = fixed_offer(
        offer_id="c", supplier="Alfa", name="A", price=0.10, spread=0.0, fee=0.0
    )

    comparison = compare([a, b, c], profile, pun)

    assert [r.offer_id for r in comparison.results] == ["c", "b", "a"]
    assert [r.rank for r in comparison.results] == [1, 2, 3]
    assert comparison.results[0].delta_vs_best_eur == 0.0


def test_break_even_pun_matches_variable_and_fixed_cost():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    fixed = fixed_offer(offer_id="fixed", price=0.15, spread=0.0, fee=50.0)
    var = variable_offer(offer_id="var", spread=0.03, fee=20.0)

    comparison = compare([fixed, var], profile, pun)
    var_result = next(r for r in comparison.results if r.offer_id == "var")
    break_even = var_result.break_even_pun_eur_kwh
    assert break_even is not None

    # At the break-even PUN, cost with a flat scenario should equal the
    # fixed offer's cost.
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


def test_break_even_pun_none_when_no_fixed_offer():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    var = variable_offer()

    comparison = compare([var], profile, pun)

    assert comparison.results[0].break_even_pun_eur_kwh is None


def test_eur_per_kwh_effective():
    profile = make_profile([100.0] * 12)  # 1200 kWh
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(price=0.10, spread=0.0, fee=120.0)

    comparison = compare([offer], profile, pun)

    # cost = 1200*0.10 + 120 = 240; eur/kwh = 240/1200 = 0.20
    assert comparison.results[0].eur_per_kwh_effective == pytest.approx(0.20)
