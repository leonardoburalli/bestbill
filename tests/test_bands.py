import pytest

from bestbill.core.bands import (
    DEFAULT_HOUSEHOLD_SPLIT,
    aggregate_to_structure,
    split_month_to_bands,
)
from bestbill.core.models import Band, BandStructure, MonthlyConsumption

from .helpers import month


def test_split_uses_default_household_split_when_no_bands():
    m = MonthlyConsumption(month=month(2024, 9), kwh=100.0)
    bands = split_month_to_bands(m)
    assert bands[Band.F1] == pytest.approx(100.0 * DEFAULT_HOUSEHOLD_SPLIT[Band.F1])
    assert bands[Band.F2] == pytest.approx(100.0 * DEFAULT_HOUSEHOLD_SPLIT[Band.F2])
    assert bands[Band.F3] == pytest.approx(100.0 * DEFAULT_HOUSEHOLD_SPLIT[Band.F3])
    assert sum(bands.values()) == pytest.approx(100.0)


def test_split_uses_user_bands_when_present():
    m = MonthlyConsumption(
        month=month(2024, 9), kwh=100.0, bands={"F1": 40.0, "F2": 30.0, "F3": 30.0}
    )
    bands = split_month_to_bands(m)
    assert bands == {Band.F1: 40.0, Band.F2: 30.0, Band.F3: 30.0}


def test_aggregate_mono_sums_all_bands():
    band_kwh = {Band.F1: 10.0, Band.F2: 20.0, Band.F3: 30.0}
    assert aggregate_to_structure(band_kwh, BandStructure.MONO) == {"mono": 60.0}


def test_aggregate_f1f2f3_passthrough():
    band_kwh = {Band.F1: 10.0, Band.F2: 20.0, Band.F3: 30.0}
    assert aggregate_to_structure(band_kwh, BandStructure.F1F2F3) == {
        "F1": 10.0,
        "F2": 20.0,
        "F3": 30.0,
    }


def test_aggregate_f1f23_combines_f2_and_f3():
    band_kwh = {Band.F1: 10.0, Band.F2: 20.0, Band.F3: 30.0}
    assert aggregate_to_structure(band_kwh, BandStructure.F1F23) == {
        "F1": 10.0,
        "F23": 50.0,
    }
