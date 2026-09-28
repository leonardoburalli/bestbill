"""Split monthly consumption into F1/F2/F3 bands, or aggregate to an offer's
band structure.
"""

from __future__ import annotations

from bestbill.core.models import Band, BandStructure, MonthlyConsumption

#: Standard household time-of-use split, used when the user hasn't entered
#: their own F1/F2/F3 breakdown from the bill.
#: TODO(source): confirm with ARERA reference split (placeholder values).
DEFAULT_HOUSEHOLD_SPLIT: dict[Band, float] = {
    Band.F1: 0.33,
    Band.F2: 0.31,
    Band.F3: 0.36,
}


def split_month_to_bands(month: MonthlyConsumption) -> dict[Band, float]:
    """Return F1/F2/F3 kWh for a month: the user's own bands if given, else
    the standard household split applied to the month's total kWh.
    """
    if month.bands is not None:
        return dict(month.bands)
    return {
        band: month.kwh * fraction for band, fraction in DEFAULT_HOUSEHOLD_SPLIT.items()
    }


def aggregate_to_structure(
    band_kwh: dict[Band, float], structure: BandStructure
) -> dict[str, float]:
    """Aggregate F1/F2/F3 kWh into the keys expected by an offer's band
    structure (mono, f1f2f3, or f1f23).
    """
    f1 = band_kwh.get(Band.F1, 0.0)
    f2 = band_kwh.get(Band.F2, 0.0)
    f3 = band_kwh.get(Band.F3, 0.0)

    if structure is BandStructure.MONO:
        return {"mono": f1 + f2 + f3}
    if structure is BandStructure.F1F2F3:
        return {"F1": f1, "F2": f2, "F3": f3}
    if structure is BandStructure.F1F23:
        return {"F1": f1, "F23": f2 + f3}
    raise ValueError(f"unsupported band structure: {structure!r}")
