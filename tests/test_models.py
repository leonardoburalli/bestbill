import json
from datetime import date

import pytest
from pydantic import ValidationError

from bestbill.core.models import (
    ConsumptionProfile,
    Flat,
    MonthlyConsumption,
    Offer,
    PunSeries,
    Scaled,
)

from .helpers import fixed_offer, month


def test_fixed_offer_requires_matching_energy_price_keys():
    with pytest.raises(ValidationError):
        Offer(
            id="x",
            supplier="A",
            name="A",
            source="placet",
            price_type="fixed",
            band_structure="f1f2f3",
            energy_price_eur_kwh={"F1": 0.1},  # missing F2, F3
            spread_eur_kwh={"F1": 0.0, "F2": 0.0, "F3": 0.0},
            fixed_fee_eur_year=0,
        )


def test_variable_offer_must_not_set_energy_price():
    with pytest.raises(ValidationError):
        Offer(
            id="x",
            supplier="A",
            name="A",
            source="placet",
            price_type="variable",
            band_structure="mono",
            energy_price_eur_kwh={"mono": 0.1},
            spread_eur_kwh={"mono": 0.02},
            fixed_fee_eur_year=0,
        )


def test_offer_negative_fee_rejected():
    with pytest.raises(ValidationError):
        fixed_offer(fee=-1)


def test_offer_valid_from_after_valid_to_rejected():
    with pytest.raises(ValidationError):
        fixed_offer(valid_from=date(2025, 1, 1), valid_to=date(2024, 1, 1))


def test_monthly_consumption_bands_must_sum_to_kwh():
    with pytest.raises(ValidationError):
        MonthlyConsumption(
            month=month(2024, 9),
            kwh=100,
            bands={"F1": 10, "F2": 10, "F3": 10},  # sums to 30, not 100
        )


def test_monthly_consumption_bands_within_tolerance_ok():
    # 0.4% off, within the 0.5% tolerance
    MonthlyConsumption(
        month=month(2024, 9),
        kwh=100,
        bands={"F1": 33.2, "F2": 33.2, "F3": 33.2},
    )


def test_monthly_consumption_month_must_be_first_of_month():
    with pytest.raises(ValidationError):
        MonthlyConsumption(month=date(2024, 9, 15), kwh=100)


def test_profile_rejects_11_distinct_months():
    months = [MonthlyConsumption(month=month(2024, m), kwh=100.0) for m in range(1, 12)]
    with pytest.raises(ValidationError):
        ConsumptionProfile(months=months)


def test_profile_rejects_duplicate_months():
    months = [MonthlyConsumption(month=month(2024, 1), kwh=100.0) for _ in range(12)]
    with pytest.raises(ValidationError):
        ConsumptionProfile(months=months)


def test_profile_rejects_non_consecutive_months():
    months = [MonthlyConsumption(month=month(2024, m), kwh=100.0) for m in range(1, 13)]
    # break consecutiveness: swap month 6 for a non-adjacent one
    months[5] = MonthlyConsumption(month=month(2025, 6), kwh=100.0)
    with pytest.raises(ValidationError):
        ConsumptionProfile(months=months)


def test_profile_accepts_12_consecutive_months_regardless_of_input_order():
    ms = [MonthlyConsumption(month=month(2024, m), kwh=float(m)) for m in range(1, 13)]
    shuffled = [ms[5], ms[0], ms[11]] + ms[1:5] + ms[6:11]
    profile = ConsumptionProfile(months=shuffled)
    assert profile.period_start == month(2024, 1)
    assert profile.period_end == month(2024, 12)
    assert profile.total_kwh == sum(range(1, 13))


def test_pun_series_keys_must_be_first_of_month():
    with pytest.raises(ValidationError):
        PunSeries(values={date(2024, 9, 15): 0.12})


def test_scaled_scenario_requires_positive_factor():
    with pytest.raises(ValidationError):
        Scaled(factor=0)


def test_flat_scenario_requires_nonnegative_value():
    with pytest.raises(ValidationError):
        Flat(value=-0.01)


def test_offer_json_without_duration_keys_loads_with_defaults():
    from bestbill.core.models import Offer
    from tests.helpers import fixed_offer

    data = json.loads(fixed_offer().model_dump_json())
    data.pop("duration_months")
    data.pop("duration_open_ended")
    offer = Offer.model_validate_json(json.dumps(data))
    assert offer.duration_months is None
    assert offer.duration_open_ended is False


def test_guarantees_min_duration_semantics():
    from tests.helpers import fixed_offer

    base = fixed_offer()
    assert base.guarantees_min_duration(12) is False  # unknown
    assert base.model_copy(update={"duration_months": 12}).guarantees_min_duration(12)
    assert not base.model_copy(update={"duration_months": 12}).guarantees_min_duration(
        13
    )
    open_ended = base.model_copy(
        update={"duration_months": 36, "duration_open_ended": True}
    )
    assert open_ended.guarantees_min_duration(1) is False


def test_duration_within_semantics():
    from tests.helpers import fixed_offer

    base = fixed_offer()
    twelve = base.model_copy(update={"duration_months": 12})
    thirty_six = base.model_copy(update={"duration_months": 36})
    open_ended = base.model_copy(update={"duration_open_ended": True})
    # no bound: everything passes, including unknown and open-ended
    assert base.duration_within(None, None)
    assert open_ended.duration_within(None, None)
    # exactly 12
    assert twelve.duration_within(12, 12)
    assert not thirty_six.duration_within(12, 12)
    # more than 12
    assert thirty_six.duration_within(13, None)
    assert not twelve.duration_within(13, None)
    # unknown / open-ended never pass a bound
    assert not base.duration_within(None, 120)
    assert not open_ended.duration_within(1, None)
