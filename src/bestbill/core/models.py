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
    "CustomerType",
    "Residency",
    "GeoLevel",
    "ComuneRef",
    "GeoRestriction",
    "LossesMode",
    "DiscountValidity",
    "DiscountUnit",
    "Discount",
    "ConsumptionTier",
    "SupplierNameSource",
    "BreakEvenStatus",
    "Offer",
    "MonthlyConsumption",
    "ConsumptionProfile",
    "PunSeries",
    "Historical",
    "Scaled",
    "Flat",
    "Scenario",
    "CostBreakdown",
    "OfferResult",
    "Assumptions",
    "Comparison",
]

#: Label for the cost this engine estimates -- shown next to every total in
#: the CLI/API/assumptions. Never the full electricity bill (see
#: ``Offer``'s and ``compare()``'s docstrings).
COST_LABEL = "costo materia energia (IVA esclusa)"


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


class CustomerType(StrEnum):
    """ARERA TIPO_CLIENTE: 01 domestic, 02 non-domestic."""

    DOMESTIC = "domestic"
    NON_DOMESTIC = "non_domestic"


class SupplierNameSource(StrEnum):
    """Where an offer's ``supplier`` display name came from, in resolution
    order (see ``bestbill.arera.operators`` and ``bestbill.catalog.build``):

    - ``ARERA``: the ARERA "Ricerca operatori" export (RAGIONE SOCIALE),
      matched by VAT (PARTITA IVA).
    - ``PLACET``: a PLACET row's ``denominazione`` for the same VAT
      (mercato libero offers only -- PLACET offers always use ``ARERA``
      or their own ``denominazione`` directly is treated as ``PLACET``).
    - ``DOMAIN``: the retailer's website domain, from
      ``URL_SITO_VENDITORE``, stripped of scheme/``www.``/path.
    - ``VAT``: last resort, ``"P.IVA <vat>"``.
    """

    ARERA = "arera"
    PLACET = "placet"
    DOMAIN = "domain"
    VAT = "vat"


class BreakEvenStatus(StrEnum):
    """Classifies a variable offer's break-even PUN against the cheapest
    eligible fixed offer (see ``bestbill.core.calculator._break_even_pun``):

    - ``CHEAPER_BELOW``: the normal case -- the variable offer is cheaper
      than the best fixed offer for PUN values below the break-even point
      (and more expensive above it).
    - ``NEVER_CHEAPER``: the break-even PUN is <= 0 -- the variable offer
      is never cheaper than the best fixed offer at any non-negative PUN.
    - ``ALWAYS_CHEAPER``: the variable offer's cost slope (kWh × loss
      multiplier) is <= 0, so it can't be compared as a break-even point;
      in practice this only happens when there's no fixed offer to break
      even against or the variable offer has zero/negative consumption
      exposure -- kept for completeness, see the calculator docstring.
    """

    CHEAPER_BELOW = "cheaper_below"
    NEVER_CHEAPER = "never_cheaper"
    ALWAYS_CHEAPER = "always_cheaper"


class Residency(StrEnum):
    """ARERA DOMESTICO_RESIDENTE: who the offer is restricted to."""

    RESIDENTS = "residents"
    NON_RESIDENTS = "non_residents"
    ANY = "any"


class GeoLevel(StrEnum):
    """ARERA ZoneOfferta levels."""

    REGIONE = "regione"
    PROVINCIA = "provincia"
    COMUNE = "comune"


class ComuneRef(BaseModel):
    """A comune with its administrative hierarchy (see ``bestbill.geo``):
    6-digit ISTAT comune code, 3-digit provincia code (the first 3 digits
    of the comune code, as used by ARERA's ``PROVINCIA``) and 2-digit
    regione code (ARERA's ``REGIONE``). ``regione`` is ``None`` when the
    comune isn't in the ISTAT table (regione restrictions then can't match).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    codice: str
    provincia: str
    regione: str | None = None


class GeoRestriction(BaseModel):
    """An offer's geographic restriction: national if all sets are empty,
    otherwise the offer is only available where at least one code matches
    the user's comune, its provincia or its regione.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    regioni: frozenset[str] = frozenset()
    province: frozenset[str] = frozenset()
    comuni: frozenset[str] = frozenset()

    def matches(self, comune: ComuneRef) -> bool:
        return (
            comune.codice in self.comuni
            or comune.provincia in self.province
            or (comune.regione is not None and comune.regione in self.regioni)
        )


class LossesMode(StrEnum):
    """How the engine applies network losses (1 + LOSSES, see
    ``bestbill.arera.policy``) to an offer's energy terms. Verified against
    AU "Regole per il calcolo della spesa annua stimata" v4.0:

    - ``NONE``: no losses (fixed offers of both ARERA sources; every
      custom/legacy offer).
    - ``INDEX_ONLY``: losses apply to the index only, not the spread
      (mercato libero variable offers).
    - ``INDEX_AND_SPREAD``: losses apply to (index + spread) together
      (PLACET variable offers, i.e. PINGM + alpha).
    """

    NONE = "none"
    INDEX_ONLY = "index_only"
    INDEX_AND_SPREAD = "index_and_spread"


class DiscountValidity(StrEnum):
    """ARERA Sconto/VALIDITA."""

    ON_ENTRY = "on_entry"
    WITHIN_12_MONTHS = "within_12_months"
    BEYOND_12_MONTHS = "beyond_12_months"


class DiscountUnit(StrEnum):
    """ARERA UNITA_MISURA, as used under Sconto/PrezziSconto."""

    EUR_YEAR = "eur_year"
    EUR_KW_YEAR = "eur_kw_year"
    EUR_KWH = "eur_kwh"
    EUR_SMC = "eur_smc"
    EUR_ONE_OFF = "eur_one_off"
    PERCENT = "percent"


class Discount(BaseModel):
    """A commercial discount (Sconto). Unconditional first-12-month
    discounts are priced into the estimate by the engine (see
    ``bestbill.arera.policy``); conditional discounts are kept for display
    only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    validity: DiscountValidity
    conditional: bool
    amount: float
    unit: DiscountUnit
    applies_before_vat: bool = True
    #: Annual-consumption band this discount applies to (ARERA
    #: Sconto/PrezziSconto VALIDO_DA/VALIDO_FINO), only meaningful for
    #: ``DiscountUnit.EUR_KWH``: the discount applies to the kWh consumed
    #: within [consumption_from_kwh, consumption_to_kwh) of the customer's
    #: annual consumption. Multiple ``PrezziSconto`` tiers on the same
    #: ``Sconto`` become separate ``Discount`` objects and are additive
    #: over their ranges (see ``bestbill.arera.policy``). ``None`` means no
    #: band restriction (the whole annual consumption).
    consumption_from_kwh: float | None = Field(default=None, ge=0)
    consumption_to_kwh: float | None = Field(default=None, ge=0)
    #: First N months (from activation) this discount is valid for (ARERA
    #: Sconto/PeriodoValidita/DURATA, only ever observed on €/kWh
    #: discounts); ``None`` means the whole 12-month estimate window.
    duration_months: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _consumption_band_is_valid(self) -> Discount:
        if (
            self.consumption_from_kwh is not None
            and self.consumption_to_kwh is not None
            and self.consumption_from_kwh > self.consumption_to_kwh
        ):
            raise ValueError("consumption_from_kwh must be <= consumption_to_kwh")
        return self


class ConsumptionTier(BaseModel):
    """A consumption-based price tier (ARERA IntervalloPrezzi
    CONSUMO_DA/CONSUMO_A): the price applies to the portion of the
    offer's own band annual consumption within
    ``[from_kwh, to_kwh)`` (``to_kwh=None`` means unbounded). Tiers on the
    same band are additive over their ranges (marginal, like a tax
    bracket, confirmed by the ATENA/000190 sample offers' own
    descriptions -- see docs/pricing-policy.md); *inferred* since the AU
    "Regole per il calcolo della spesa annua stimata" v4.0 copy available
    to this importer only names "scaglioni di consumo" without a full
    worked formula.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_kwh: float = Field(ge=0)
    to_kwh: float | None = Field(default=None, ge=0)
    price_eur_kwh: float

    @model_validator(mode="after")
    def _range_is_valid(self) -> ConsumptionTier:
        if self.to_kwh is not None and self.to_kwh < self.from_kwh:
            raise ValueError("to_kwh must be >= from_kwh")
        return self


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


class Offer(BaseModel):
    """A normalised electricity offer, from ARERA data or a custom source.

    Scope: every priced field on this model is **retailer-dependent**
    (energy price/spread, supplier fees, supplier-set €/kWh extras, power
    fees, discounts) -- the commodity/supplier part of the bill. Network
    charges, system charges, excise duties and VAT are the same for every
    supplier by law and are never modelled here (see PLAN.md §5 and
    ``bestbill.core.calculator.compare``'s docstring).
    """

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
    #: Consumption-tiered ADDITIONS to ``energy_price_eur_kwh`` per band
    #: (ARERA IntervalloPrezzi CONSUMO_DA/CONSUMO_A, fixed offers only --
    #: see ``ConsumptionTier`` and ``bestbill.arera.policy``). The final
    #: per-band price is ``energy_price_eur_kwh[band] * kwh_in_band +
    #: tiered_annual_value(energy_price_tiers_eur_kwh[band], kwh_in_band)``.
    #: Empty for every band that has no tiered pricing.
    energy_price_tiers_eur_kwh: dict[str, list[ConsumptionTier]] = Field(
        default_factory=dict
    )
    #: Same as ``energy_price_tiers_eur_kwh`` but for ``spread_eur_kwh``
    #: (variable offers, or the MACROAREA 04/06 spread on fixed offers).
    spread_tiers_eur_kwh: dict[str, list[ConsumptionTier]] = Field(default_factory=dict)
    #: Annual fixed commercial fee, already converted to €/year.
    fixed_fee_eur_year: float = Field(ge=0)
    #: Other per-kWh extras already in €/kWh (dispatching, capacity market,
    #: renewable price, etc. -- see ``bestbill.arera.policy``).
    per_kwh_extras_eur: float = 0.0
    #: Annual power fee, €/kW/year (ARERA UNITA_MISURA 02); priced against a
    #: committed power input at compare() time (default 3 kW).
    power_fee_eur_kw_year: float = 0.0
    #: One-off fee, €, ADDED to the 12-month cost total (ARERA MACROAREA 01
    #: UM 05 / MACROAREA 05 UM 05 -- see docs/pricing-policy.md §5). Still
    #: reported separately in ``OfferResult.one_off_fee_eur`` for display.
    one_off_fee_eur: float = 0.0
    #: Commercial discounts; only unconditional first-12-month ones are
    #: priced (see ``bestbill.arera.policy``), the rest are kept for display.
    discounts: list[Discount] = Field(default_factory=list)

    #: Dispatching (TIPO_DISPACCIAMENTO) cost, precomputed by the parsers
    #: from the ARERA parameters files (see ``bestbill.arera.policy`` and
    #: ``bestbill.arera.parameters``). Already includes losses where the
    #: dispatching table calls for them -- the calculator must NOT apply
    #: losses again to these two fields.
    dispatching_eur_kwh: float = 0.0
    dispatching_eur_year: float = 0.0
    #: Named component values (e.g. {"msd": ..., "modeol": ...}) kept for
    #: display/debugging; not used in the cost calculation itself.
    dispatching_breakdown: dict[str, float] = Field(default_factory=dict)
    #: True if the dispatching value is an approximation (TIPO_DISPACCIAMENTO
    #: 09, Capacity Market mean applied to all 12 months instead of the
    #: current quarter only -- see docs/pricing-policy.md).
    dispatching_approximate: bool = False

    #: ARERA TIPO_CLIENTE. MVP only prices domestic offers.
    customer: CustomerType = CustomerType.DOMESTIC
    #: ARERA DOMESTICO_RESIDENTE eligibility restriction.
    residency: Residency = Residency.ANY
    #: ARERA ZoneOfferta; ``None`` means a national offer.
    geo: GeoRestriction | None = None
    #: How the engine applies network losses (1 + LOSSES) to this offer's
    #: energy terms; see ``bestbill.arera.policy`` and ``LossesMode``.
    #: Custom (legacy Excel) offers default to NONE to keep their
    #: historical, loss-free pricing.
    losses_mode: LossesMode = LossesMode.NONE

    consumption_min_kwh: float | None = Field(default=None, ge=0)
    consumption_max_kwh: float | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None

    #: Months the economic conditions are guaranteed. ``None`` with
    #: ``duration_open_ended=False`` means unknown. Old catalogues lack these
    #: keys and load with the defaults.
    duration_months: int | None = Field(default=None, ge=1)
    #: True when the offer has no fixed term (indeterminata).
    duration_open_ended: bool = False

    #: Retailer VAT number (11 digits, zero-padded), when known. ARERA
    #: mercato libero XML only publishes PIVA_UTENTE; PLACET CSV publishes
    #: both ``p_iva`` and ``denominazione`` directly.
    supplier_vat: str | None = None
    #: Where ``supplier`` came from -- see ``SupplierNameSource`` and
    #: ``bestbill.arera.operators``. ``None`` for custom (legacy Excel)
    #: offers and the rare mercato libero offer with no VAT at all.
    supplier_name_source: SupplierNameSource | None = None
    #: True for a custom (legacy Excel) offer priced with the standard
    #: household dispatching (``--include-custom``, see
    #: ``bestbill.cli``), for display/transparency only.
    dispatching_is_standard_estimate: bool = False

    def guarantees_min_duration(self, min_months: int) -> bool:
        """True if conditions are guaranteed for a fixed period of at least
        ``min_months``. Open-ended and unknown durations never qualify."""
        return (
            not self.duration_open_ended
            and self.duration_months is not None
            and self.duration_months >= min_months
        )

    def duration_within(self, min_months: int | None, max_months: int | None) -> bool:
        """True if no bound is given, or if the conditions are guaranteed for
        a fixed period within [min_months, max_months]. Open-ended and
        unknown durations never qualify once a bound is set."""
        if min_months is None and max_months is None:
            return True
        if self.duration_open_ended or self.duration_months is None:
            return False
        return (min_months is None or self.duration_months >= min_months) and (
            max_months is None or self.duration_months <= max_months
        )

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

        tier_bands = set(self.energy_price_tiers_eur_kwh) | set(
            self.spread_tiers_eur_kwh
        )
        if tier_bands - expected:
            raise ValueError(
                f"tier bands {sorted(tier_bands - expected)} not in "
                f"band_structure {self.band_structure!r} (expected {sorted(expected)})"
            )
        if self.price_type is PriceType.VARIABLE and self.energy_price_tiers_eur_kwh:
            raise ValueError(
                "variable offers must not set energy_price_tiers_eur_kwh "
                "(price comes from PUN + spread)"
            )

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


class CostBreakdown(BaseModel):
    """Decomposition of an offer's ``cost_eur`` into its ARERA-policy
    parts. ``energy + fixed_fees + per_kwh_extras + power_fee +
    dispatching + one_off - discounts == total`` (within floating-point
    tolerance) -- see ``bestbill.core.calculator`` and
    ``docs/pricing-policy.md`` §7.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    energy: float
    fixed_fees: float
    per_kwh_extras: float
    power_fee: float
    dispatching: float
    one_off: float
    discounts: float
    total: float


class OfferResult(BaseModel):
    """Ranking result for one offer. ``cost_eur`` is the estimated annual
    **commodity/supplier cost** (energy + supplier fees/extras/dispatching/
    one-off/discounts) only -- it never includes network charges, system
    charges, excise duties or VAT, which are identical across suppliers
    and don't affect the ranking (see ``compare()``'s docstring).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    offer_id: str
    supplier: str
    name: str
    price_type: PriceType
    cost_eur: float
    delta_vs_best_eur: float
    eur_per_kwh_effective: float
    #: Advertised unit energy price (€/kWh, before VAT): consumption-weighted
    #: listed price for fixed offers, or spread over PUN for variable offers.
    #: Excludes discounts, fixed fees, per-kWh extras, dispatching, power fee
    #: and losses (and the PUN index itself).
    energy_price_eur_kwh: float
    energy_price_kind: Literal["fixed", "pun_spread"]
    rank: int = Field(ge=1)
    break_even_pun_eur_kwh: float | None = None
    #: Why ``break_even_pun_eur_kwh`` is (or isn't) set -- see
    #: ``BreakEvenStatus``. ``None`` for fixed offers.
    break_even_status: BreakEvenStatus | None = None
    #: One-off fee, included in ``cost_eur`` (see ``breakdown.one_off``)
    #: and also reported here for convenience/display.
    one_off_fee_eur: float = 0.0
    #: Conditional discounts kept for display only (not priced).
    conditional_discounts: list[Discount] = Field(default_factory=list)
    breakdown: CostBreakdown
    #: True if this offer's dispatching cost is the catalogue's standard
    #: household estimate rather than its own (custom/legacy offers priced
    #: with ``--include-custom``, see ``bestbill.cli``), for display only.
    dispatching_is_standard_estimate: bool = False
    #: See ``Offer.duration_months`` / ``Offer.duration_open_ended``.
    duration_months: int | None = None
    duration_open_ended: bool = False


class Assumptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    period_start: date
    period_end: date
    pun_months_used: dict[date, float]
    substituted_pun_months: list[date]
    band_split_source: Literal["user", "standard"]
    scenario: Scenario
    statement: str
    committed_power_kw: float = 3.0
    residency: Literal["resident", "non_resident"] = "resident"
    istat_comune: str | None = None
    #: What every cost in this comparison measures (see ``COST_LABEL``);
    #: never the full electricity bill.
    cost_label: str = COST_LABEL


class Comparison(BaseModel):
    """The ranked result of :func:`bestbill.core.calculator.compare`.
    Every cost in ``results`` is the commodity/supplier cost only (see
    ``OfferResult``); it is not the full electricity bill.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: list[OfferResult]
    assumptions: Assumptions
    excluded: list[tuple[str, str]]
