"""Request/response models of the API (also the source of ``openapi.json``)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from bestbill.core.models import (
    Assumptions,
    Band,
    BandStructure,
    BreakEvenStatus,
    CostBreakdown,
    Discount,
    Historical,
    MonthlyConsumption,
    OfferSource,
    PriceType,
    Scenario,
    SupplierNameSource,
)

_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
MonthStr = Annotated[str, Field(pattern=_MONTH_PATTERN, examples=["2025-09"])]
Kwh = Annotated[float, Field(ge=0, le=100_000, allow_inf_nan=False)]

BAND_TOLERANCE_MESSAGE = (
    "La somma di F1, F2 e F3 deve coincidere con i kWh totali del mese "
    "(tolleranza 0,5%)."
)


def parse_month(value: str) -> date:
    year, month = value.split("-")
    return date(int(year), int(month), 1)


# -- health / meta -----------------------------------------------------------
class Health(BaseModel):
    status: Literal["ok"] = "ok"
    catalog_loaded: bool
    snapshot_date: date | None = None
    catalog_age_days: int | None = None


class CatalogSource(BaseModel):
    name: str
    url: str | None = None
    licence: str | None = None
    file_date: date | None = None


class CatalogCounts(BaseModel):
    included: int
    included_by_source: dict[str, int]
    excluded: int
    excluded_by_reason: dict[str, int]


class CatalogMeta(BaseModel):
    snapshot_date: date
    age_days: int
    stale: bool = Field(description="True when the snapshot is older than 3 days.")
    counts: CatalogCounts
    sources: list[CatalogSource]
    licence: str | None = None
    attribution: str


# -- offers / comuni / sample ------------------------------------------------
class OfferListItem(BaseModel):
    id: str
    supplier: str
    name: str
    url: str | None
    price_type: PriceType
    band_structure: BandStructure
    source: OfferSource
    valid_to: date | None


class OfferPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[OfferListItem]


class ComuneOut(BaseModel):
    codice: str = Field(description="6-digit ISTAT comune code.")
    nome: str
    sigla_provincia: str
    regione: str


class SampleMonth(BaseModel):
    month: MonthStr
    kwh: float
    pun: float | None = None


class SampleHousehold(BaseModel):
    location: str
    description: str
    months: list[SampleMonth]


class ParsedProfile(BaseModel):
    location: str
    months: list[SampleMonth]


class ParseResult(BaseModel):
    profiles: list[ParsedProfile]
    skipped: list[str] = Field(
        description="Locations found in the file but not usable (need 12 "
        "consecutive months of non-negative kWh)."
    )


# -- compare -----------------------------------------------------------------
class MonthInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: MonthStr
    kwh: Kwh
    f1: Kwh | None = None
    f2: Kwh | None = None
    f3: Kwh | None = None

    @model_validator(mode="after")
    def _bands_all_or_none(self) -> MonthInput:
        given = [b is not None for b in (self.f1, self.f2, self.f3)]
        if any(given) and not all(given):
            raise ValueError("Indica tutte e tre le fasce F1, F2 e F3, oppure nessuna.")
        return self

    @property
    def has_bands(self) -> bool:
        return self.f1 is not None

    def to_core(self) -> MonthlyConsumption:
        bands = None
        if self.f1 is not None and self.f2 is not None and self.f3 is not None:
            bands = {Band.F1: self.f1, Band.F2: self.f2, Band.F3: self.f3}
        try:
            return MonthlyConsumption(
                month=parse_month(self.month), kwh=self.kwh, bands=bands
            )
        except ValueError:
            raise ValueError(BAND_TOLERANCE_MESSAGE) from None


class CompareFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_type: PriceType | None = None
    source: Literal["placet", "mlibero"] | None = None


class CompareRequest(BaseModel):
    """12 consecutive months of household consumption. Processed in memory
    and never stored or logged.
    """

    model_config = ConfigDict(extra="forbid")

    consumption: list[MonthInput] = Field(min_length=12, max_length=12)
    residency: Literal["resident", "non_resident"] = "resident"
    istat_comune: str | None = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="6-digit ISTAT comune code; needed to see area-restricted offers.",
    )
    committed_power_kw: float = Field(default=3.0, gt=0, le=30, allow_inf_nan=False)
    scenario: Scenario = Field(default_factory=Historical)
    filters: CompareFilters = Field(default_factory=CompareFilters)
    top_n: int = Field(default=50, ge=1, le=200)

    @field_validator("consumption")
    @classmethod
    def _check_consumption(cls, consumption: list[MonthInput]) -> list[MonthInput]:
        months = [parse_month(m.month) for m in consumption]
        if len(set(months)) != len(months):
            raise ValueError("I mesi devono essere tutti diversi.")
        ordered = sorted(months)
        for a, b in zip(ordered, ordered[1:], strict=False):
            expected = (a.year + a.month // 12, a.month % 12 + 1)
            if (b.year, b.month) != expected:
                raise ValueError("Servono 12 mesi consecutivi, senza buchi.")
        if len({m.has_bands for m in consumption}) > 1:
            raise ValueError(
                "Le fasce F1/F2/F3 vanno indicate per tutti i mesi o per nessuno."
            )
        for m in consumption:
            m.to_core()
        return consumption


class ResultItem(BaseModel):
    """One ranked offer. ``cost_eur`` is the commodity/retailer cost only,
    before VAT (see ``assumptions.cost_label``); ``rank`` and
    ``delta_vs_best_eur`` are over all eligible offers, before any filter.
    """

    offer_id: str
    rank: int
    supplier: str
    name: str
    supplier_vat: str | None
    supplier_name_source: SupplierNameSource | None
    url: str | None
    source: OfferSource
    price_type: PriceType
    band_structure: BandStructure
    valid_from: date | None
    valid_to: date | None
    cost_eur: float
    delta_vs_best_eur: float
    eur_per_kwh_effective: float
    breakdown: CostBreakdown
    break_even_pun_eur_kwh: float | None
    break_even_status: BreakEvenStatus | None
    one_off_fee_eur: float
    conditional_discounts: list[Discount]
    dispatching_is_standard_estimate: bool


class CompareResponse(BaseModel):
    snapshot_date: date
    assumptions: Assumptions
    total_eligible: int = Field(description="Offers eligible for this household.")
    total_matching: int = Field(description="Eligible offers matching the filters.")
    results: list[ResultItem]
    excluded_count: int
    excluded_by_reason: dict[str, int]


class ErrorDetail(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: list[ErrorDetail]


class ErrorResponse(BaseModel):
    detail: str
