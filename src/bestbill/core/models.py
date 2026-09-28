"""Core domain model: offers, consumption, PUN, scenarios and results.

Pure Pydantic v2 models, frozen and immutable. No web or I/O dependencies.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "Band",
    "BandStructure",
    "PriceType",
    "OfferSource",
    "Offer",
    "MonthlyConsumption",
    "ConsumptionProfile",
    "PunSeries",
    "Historical",
    "Scaled",
    "Flat",
    "Scenario",
    "OfferResult",
    "Assumptions",
    "Comparison",
]


class Band(StrEnum):
    """Time-of-use band recorded on a bill (F1/F2/F3)."""

    F1 = "F1"
    F2 = "F2"
    F3 = "F3"


class BandStructure(StrEnum):
    """How an offer's energy price is split across bands."""

    MONO = "mono"
    F1F2F3 = "f1f2f3"
    F1F23 = "f1f23"


#: Expected keys of ``energy_price_eur_kwh`` / ``spread_eur_kwh`` for each
#: band structure.
EXPECTED_BAND_KEYS: dict[BandStructure, frozenset[str]] = {
    BandStructure.MONO: frozenset({"mono"}),
    BandStructure.F1F2F3: frozenset({"F1", "F2", "F3"}),
    BandStructure.F1F23: frozenset({"F1", "F23"}),
}


class PriceType(StrEnum):
    FIXED = "fixed"
    VARIABLE = "variable"


class OfferSource(StrEnum):
    PLACET = "placet"
    MLIBERO = "mlibero"
    CUSTOM = "custom"


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


class Offer(BaseModel):
    """A normalised electricity offer, from ARERA data or a custom source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    supplier: str
    name: str
    url: str | None = None
    source: OfferSource
    price_type: PriceType
    band_structure: BandStructure

    #: €/kWh price per band, required (and only meaningful) for fixed offers.
    energy_price_eur_kwh: dict[str, float] = Field(default_factory=dict)
    #: €/kWh spread added on top of PUN (variable) or the fixed price (fixed).
    spread_eur_kwh: dict[str, float] = Field(default_factory=dict)
    #: Annual fixed commercial fee, already converted to €/year.
    fixed_fee_eur_year: float = Field(ge=0)
    #: Other per-kWh extras (dispatching, capacity market, etc.).
    other_per_kwh_eur: float = 0.0

    consumption_min_kwh: float | None = Field(default=None, ge=0)
    consumption_max_kwh: float | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def _check_bands_and_prices(self) -> Offer:
        expected = EXPECTED_BAND_KEYS[self.band_structure]

        spread_keys = set(self.spread_eur_kwh)
        if spread_keys != set(expected):
            raise ValueError(
                f"spread_eur_kwh keys {sorted(spread_keys)} do not match "
                f"band_structure {self.band_structure!r} (expected "
                f"{sorted(expected)})"
            )

        if self.price_type is PriceType.FIXED:
            price_keys = set(self.energy_price_eur_kwh)
            if price_keys != set(expected):
                raise ValueError(
                    "fixed offers require energy_price_eur_kwh keys matching "
                    f"band_structure {self.band_structure!r} (expected "
                    f"{sorted(expected)}, got {sorted(price_keys)})"
                )
            for band, price in self.energy_price_eur_kwh.items():
                if price < 0:
                    raise ValueError(f"energy price for {band!r} must be >= 0")
        else:
            if self.energy_price_eur_kwh:
                raise ValueError(
                    "variable offers must not set energy_price_eur_kwh "
                    "(price comes from PUN + spread)"
                )

        for band, spread in self.spread_eur_kwh.items():
            if self.price_type is PriceType.FIXED and spread < 0:
                raise ValueError(f"spread for {band!r} must be >= 0")

        if (
            self.consumption_min_kwh is not None
            and self.consumption_max_kwh is not None
            and self.consumption_min_kwh > self.consumption_max_kwh
        ):
            raise ValueError("consumption_min_kwh must be <= consumption_max_kwh")

        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from > self.valid_to
        ):
            raise ValueError("valid_from must be <= valid_to")

        return self


class MonthlyConsumption(BaseModel):
    """Consumption for a single calendar month."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    month: date
    kwh: float = Field(ge=0)
    bands: dict[Band, float] | None = None

    @field_validator("month")
    @classmethod
    def _month_is_first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("month must be the first day of the calendar month")
        return value

    @model_validator(mode="after")
    def _bands_sum_to_kwh(self) -> MonthlyConsumption:
        if self.bands is None:
            return self
        band_total = sum(self.bands.values())
        if any(v < 0 for v in self.bands.values()):
            raise ValueError("band kWh values must be >= 0")
        tolerance = max(0.005 * self.kwh, 1e-9)
        if abs(band_total - self.kwh) > tolerance:
            raise ValueError(
                f"bands sum to {band_total} kWh, expected {self.kwh} kWh (within 0.5%)"
            )
        return self


class ConsumptionProfile(BaseModel):
    """Exactly 12 consecutive calendar months of consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    months: list[MonthlyConsumption]

    @model_validator(mode="after")
    def _exactly_twelve_consecutive_months(self) -> ConsumptionProfile:
        ordered = sorted(self.months, key=lambda m: m.month)
        seen = [m.month for m in ordered]
        if len(seen) != len(set(seen)):
            raise ValueError("consumption months must be distinct")
        if len(ordered) != 12:
            raise ValueError(
                f"consumption profile must have exactly 12 months, got {len(ordered)}"
            )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.month != _next_month(previous.month):
                raise ValueError(
                    "consumption months must be 12 consecutive calendar months "
                    f"(gap between {previous.month} and {current.month})"
                )
        object.__setattr__(self, "months", ordered)
        return self

    @property
    def total_kwh(self) -> float:
        return sum(m.kwh for m in self.months)

    @property
    def period_start(self) -> date:
        return self.months[0].month

    @property
    def period_end(self) -> date:
        return self.months[-1].month


class PunSeries(BaseModel):
    """Monthly PUN (national single price) history, €/kWh."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: dict[date, float]

    @field_validator("values")
    @classmethod
    def _keys_are_first_of_month(cls, value: dict[date, float]) -> dict[date, float]:
        for month in value:
            if month.day != 1:
                raise ValueError("PunSeries keys must be the first day of the month")
        return value

    def get(self, month: date) -> float | None:
        return self.values.get(month)

    @property
    def is_empty(self) -> bool:
        return not self.values

    @property
    def latest_month(self) -> date | None:
        return max(self.values) if self.values else None


class Historical(BaseModel):
    """The default scenario: use the PUN actually recorded, month by month."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["historical"] = "historical"


class Scaled(BaseModel):
    """Multiply every historical PUN value by a factor (e.g. 1.2 = +20%)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["scaled"] = "scaled"
    factor: float = Field(gt=0)


class Flat(BaseModel):
    """Replace every month's PUN with a single flat value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["flat"] = "flat"
    value: float = Field(ge=0)


Scenario = Annotated[Historical | Scaled | Flat, Field(discriminator="kind")]


class OfferResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    offer_id: str
    supplier: str
    name: str
    price_type: PriceType
    cost_eur: float
    delta_vs_best_eur: float
    eur_per_kwh_effective: float
    rank: int = Field(ge=1)
    break_even_pun_eur_kwh: float | None = None


class Assumptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    period_start: date
    period_end: date
    pun_months_used: dict[date, float]
    substituted_pun_months: list[date]
    band_split_source: Literal["user", "standard"]
    scenario: Scenario
    statement: str


class Comparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    results: list[OfferResult]
    assumptions: Assumptions
    excluded: list[tuple[str, str]]
