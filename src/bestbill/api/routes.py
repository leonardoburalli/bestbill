"""Endpoints. Consumption data is handled in memory and never stored or
logged: no route logs request bodies or values derived from them.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from datetime import date
from functools import lru_cache
from importlib import resources
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)

import bestbill
from bestbill.api.catalog_source import CatalogProvider, CatalogSnapshot
from bestbill.api.schemas import (
    CatalogCounts,
    CatalogMeta,
    CatalogSource,
    CompareRequest,
    CompareResponse,
    ComuneOut,
    ErrorResponse,
    Health,
    OfferListItem,
    OfferPage,
    ResultItem,
    SampleHousehold,
    ValidationErrorResponse,
)
from bestbill.api.settings import STALE_AFTER_DAYS
from bestbill.core.calculator import compare
from bestbill.core.models import (
    ConsumptionProfile,
    OfferSource,
    PriceType,
)
from bestbill.geo import get_comune, search_comuni

router = APIRouter(prefix="/api")

NOT_LOADED = "Il catalogo delle offerte non è ancora disponibile. Riprova tra poco."
NOT_LOADED_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorResponse, "description": "Catalogue not loaded yet."}
}


def get_provider(request: Request) -> CatalogProvider:
    provider: CatalogProvider = request.app.state.provider
    return provider


def get_snapshot(
    provider: Annotated[CatalogProvider, Depends(get_provider)],
) -> CatalogSnapshot:
    snapshot = provider.snapshot
    if snapshot is None:
        raise HTTPException(status_code=503, detail=NOT_LOADED)
    return snapshot


Snapshot = Annotated[CatalogSnapshot, Depends(get_snapshot)]


def _field_error(field: str, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=[{"field": field, "message": message}])


@router.get("/health")
def health(provider: Annotated[CatalogProvider, Depends(get_provider)]) -> Health:
    snap = provider.snapshot
    return Health(
        version=bestbill.__version__,
        catalog_loaded=snap is not None,
        snapshot_date=snap.snapshot_date if snap else None,
        catalog_age_days=snap.age_days() if snap else None,
    )


@router.head("/health", include_in_schema=False)
def health_head() -> Response:
    """Liveness for uptime checkers and platforms that probe with HEAD."""
    return Response(status_code=200)


@router.get("/catalog/meta", responses=NOT_LOADED_RESPONSES)
def catalog_meta(snap: Snapshot) -> CatalogMeta:
    manifest = snap.manifest
    sources = [
        CatalogSource.model_validate(s)
        for s in manifest.get("sources", [])
        if isinstance(s, dict)
    ]
    age = snap.age_days()
    return CatalogMeta(
        snapshot_date=snap.snapshot_date,
        age_days=age,
        stale=age > STALE_AFTER_DAYS,
        counts=CatalogCounts.model_validate(snap.stats),
        sources=sources,
        licence=manifest.get("licence"),
        attribution=snap.attribution,
    )


@router.get("/offers", responses=NOT_LOADED_RESPONSES)
def list_offers(
    snap: Snapshot,
    price_type: PriceType | None = None,
    source: OfferSource | None = None,
    supplier: Annotated[str | None, Query(max_length=100)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OfferPage:
    supplier_q = supplier.casefold() if supplier else None
    name_q = q.casefold() if q else None
    matching = [
        o
        for o in snap.offers
        if (price_type is None or o.price_type is price_type)
        and (source is None or o.source is source)
        and (supplier_q is None or supplier_q in o.supplier.casefold())
        and (name_q is None or name_q in o.name.casefold())
    ]
    matching.sort(key=lambda o: (o.supplier.casefold(), o.name.casefold(), o.id))
    page = matching[offset : offset + limit]
    return OfferPage(
        total=len(matching),
        limit=limit,
        offset=offset,
        items=[
            OfferListItem(
                id=o.id,
                supplier=o.supplier,
                name=o.name,
                url=o.url,
                price_type=o.price_type,
                band_structure=o.band_structure,
                source=o.source,
                valid_to=o.valid_to,
                duration_months=o.duration_months,
                duration_open_ended=o.duration_open_ended,
            )
            for o in page
        ],
    )


@router.get("/comuni")
def comuni(
    q: Annotated[str, Query(min_length=2, max_length=60)],
) -> list[ComuneOut]:
    return [
        ComuneOut(
            codice=c.codice_comune,
            nome=c.nome,
            sigla_provincia=c.sigla_provincia,
            regione=c.nome_regione,
        )
        for c in search_comuni(q, limit=20)
    ]


def _month_str(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


@lru_cache(maxsize=1)
def _load_sample() -> SampleHousehold:
    raw = resources.files("bestbill").joinpath("data/sample.json").read_text("utf-8")
    return SampleHousehold.model_validate_json(raw)


@router.get("/sample")
def sample() -> SampleHousehold:
    return _load_sample()


def _fold(text: str) -> str:
    """Case- and accent-insensitive form for substring search."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@router.post(
    "/compare",
    responses={
        **NOT_LOADED_RESPONSES,
        413: {"model": ErrorResponse, "description": "Body over 64 KB."},
        422: {"model": ValidationErrorResponse},
    },
)
def compare_offers(body: CompareRequest, snap: Snapshot) -> CompareResponse:
    """Backtest ("perfect foresight"): what today's offers would have cost on
    your last 12 months of consumption and PUN. Commodity/retailer cost only,
    before VAT. Not a forecast.
    """
    if body.istat_comune is not None and get_comune(body.istat_comune) is None:
        raise _field_error("istat_comune", "Codice comune ISTAT sconosciuto.")

    profile = ConsumptionProfile(months=[m.to_core() for m in body.consumption])
    comparison = compare(
        list(snap.offers),
        profile,
        snap.pun,
        scenario=body.scenario,
        residency=body.residency,
        istat_comune=body.istat_comune,
        committed_power_kw=body.committed_power_kw,
    )
    by_id = {o.id: o for o in snap.offers}
    matching = [
        r
        for r in comparison.results
        if (body.filters.price_type is None or r.price_type is body.filters.price_type)
        and (
            body.filters.source is None
            or by_id[r.offer_id].source.value == body.filters.source
        )
        and by_id[r.offer_id].duration_within(
            body.filters.min_duration_months, body.filters.max_duration_months
        )
    ]
    best_cost = matching[0].cost_eur if matching else 0.0
    matching = [
        r.model_copy(update={"rank": rank, "delta_vs_best_eur": r.cost_eur - best_cost})
        for rank, r in enumerate(matching, start=1)
    ]
    hits = matching
    search_matching: int | None = None
    if body.search is not None:
        needle = _fold(body.search)
        hits = [
            r
            for r in matching
            if needle in _fold(r.supplier) or needle in _fold(r.name)
        ]
        search_matching = len(hits)
    items: list[ResultItem] = []
    for r in hits[body.offset : body.offset + body.top_n]:
        offer = by_id[r.offer_id]
        items.append(
            ResultItem(
                **r.model_dump(),
                supplier_vat=offer.supplier_vat,
                supplier_name_source=offer.supplier_name_source,
                url=offer.url,
                source=offer.source,
                band_structure=offer.band_structure,
                valid_from=offer.valid_from,
                valid_to=offer.valid_to,
            )
        )
    reasons = Counter(reason for _, reason in comparison.excluded)
    return CompareResponse(
        snapshot_date=snap.snapshot_date,
        assumptions=comparison.assumptions,
        total_eligible=len(comparison.results),
        total_matching=len(matching),
        search_matching=search_matching,
        offset=body.offset,
        results=items,
        excluded_count=len(comparison.excluded),
        excluded_by_reason=dict(reasons),
    )
