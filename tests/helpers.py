"""Shared test helpers: build consumption profiles and PUN series quickly."""

from __future__ import annotations

from datetime import date

from bestbill.core.models import (
    ConsumptionProfile,
    MonthlyConsumption,
    Offer,
    PunSeries,
)


def month(year: int, m: int) -> date:
    return date(year, m, 1)


def months_from(start: tuple[int, int], count: int = 12) -> list[date]:
    year, m = start
    result = []
    for _ in range(count):
        result.append(date(year, m, 1))
        m += 1
        if m > 12:
            m = 1
            year += 1
    return result


def make_profile(
    kwh_list: list[float],
    start: tuple[int, int] = (2024, 9),
    bands_list: list[dict[str, float]] | None = None,
) -> ConsumptionProfile:
    assert len(kwh_list) == 12
    ms = months_from(start, 12)
    entries = []
    for i, (mm, kwh) in enumerate(zip(ms, kwh_list, strict=True)):
        bands = bands_list[i] if bands_list is not None else None
        entries.append(MonthlyConsumption(month=mm, kwh=kwh, bands=bands))
    return ConsumptionProfile(months=entries)


def make_pun(
    values: list[float],
    start: tuple[int, int] = (2024, 9),
) -> PunSeries:
    ms = months_from(start, len(values))
    return PunSeries(values=dict(zip(ms, values, strict=True)))


def fixed_offer(
    offer_id: str = "fixed-1",
    supplier: str = "Alfa",
    name: str = "Alfa Fissa",
    price: float = 0.12,
    spread: float = 0.0,
    fee: float = 96.0,
    **kwargs: object,
) -> Offer:
    return Offer(
        id=offer_id,
        supplier=supplier,
        name=name,
        source="custom",
        price_type="fixed",
        band_structure="mono",
        energy_price_eur_kwh={"mono": price},
        spread_eur_kwh={"mono": spread},
        fixed_fee_eur_year=fee,
        **kwargs,  # type: ignore[arg-type]
    )


def variable_offer(
    offer_id: str = "var-1",
    supplier: str = "Beta",
    name: str = "Beta Variabile",
    spread: float = 0.02,
    fee: float = 60.0,
    **kwargs: object,
) -> Offer:
    return Offer(
        id=offer_id,
        supplier=supplier,
        name=name,
        source="custom",
        price_type="variable",
        band_structure="mono",
        energy_price_eur_kwh={},
        spread_eur_kwh={"mono": spread},
        fixed_fee_eur_year=fee,
        **kwargs,  # type: ignore[arg-type]
    )
