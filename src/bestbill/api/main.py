"""App factory. Run: ``uvicorn bestbill.api.main:app``."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import bestbill
from bestbill.api.catalog_source import CatalogProvider
from bestbill.api.middleware import (
    BodyLimitMiddleware,
    CatchAllMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from bestbill.api.routes import router
from bestbill.api.settings import Settings

log = logging.getLogger(__name__)

DESCRIPTION = (
    "Stateless API: consumption is processed in memory per request and never "
    "stored or logged. Every cost is the commodity/retailer cost only, before "
    "VAT ('costo materia energia (IVA esclusa)'), and a backtest ('perfect "
    "foresight'): the same kWh and the same monthly PUN as your last 12 "
    "months. It is not a forecast."
)


def _pointer(loc: tuple[Any, ...]) -> str:
    parts = [p for p in loc if p != "body"]
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "body"


def _message(err: dict[str, Any]) -> str:
    """Italian message for a pydantic error. Never echoes the input value."""
    kind: str = err["type"]
    ctx: dict[str, Any] = err.get("ctx") or {}
    loc = err["loc"]
    if kind == "value_error":
        msg = str(err.get("msg", ""))
        return msg.removeprefix("Value error, ") or "Valore non valido."
    if kind == "missing":
        return "Campo obbligatorio."
    if kind == "extra_forbidden":
        return "Campo non riconosciuto."
    limits = {
        "greater_than_equal": ("maggiore o uguale a", "ge"),
        "greater_than": ("maggiore di", "gt"),
        "less_than_equal": ("minore o uguale a", "le"),
        "less_than": ("minore di", "lt"),
    }
    if kind in limits:
        text, key = limits[kind]
        return f"Il valore deve essere {text} {ctx.get(key)}."
    if kind == "string_pattern_mismatch":
        if loc and loc[-1] == "month":
            return "Mese non valido: usa il formato AAAA-MM (es. 2025-09)."
        if loc and loc[-1] == "istat_comune":
            return "Il codice comune ISTAT deve avere 6 cifre."
        return "Formato non valido."
    if kind in {"too_short", "too_long"}:
        if loc and loc[-1] == "consumption":
            return "Servono esattamente 12 mesi di consumo."
        return "Numero di elementi non valido."
    if kind in {"float_parsing", "float_type", "int_parsing", "int_type"}:
        return "Deve essere un numero."
    if kind in {"finite_number"}:
        return "Deve essere un numero finito."
    if kind in {"enum", "literal_error"}:
        return f"Valore non ammesso. Valori ammessi: {ctx.get('expected', '')}."
    if kind.startswith("union_tag") or kind == "model_attributes_type":
        return "Scenario non valido: usa historical, scaled (factor) o flat (value)."
    if kind == "json_invalid":
        return "JSON non valido."
    if kind == "string_type":
        return "Deve essere un testo."
    return "Valore non valido."


def create_app(
    settings: Settings | None = None, *, provider: CatalogProvider | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    provider = provider or CatalogProvider(settings.catalog)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider.load_initial()
        task: asyncio.Task[None] | None = None
        if provider.is_remote:
            task = asyncio.create_task(_refresh_loop(provider))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="BestBill API",
        version=bestbill.__version__,
        description=DESCRIPTION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.provider = provider
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = [
            {"field": _pointer(tuple(e["loc"])), "message": _message(dict(e))}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    # Innermost first; the last one added is the outermost.
    app.add_middleware(CatchAllMiddleware)
    app.add_middleware(
        BodyLimitMiddleware,
        default_limit=settings.max_compare_body_bytes,
        path_limits={
            "/api/compare": settings.max_compare_body_bytes,
            # multipart framing overhead on top of the 2 MB file cap
            "/api/parse": settings.max_upload_bytes + 64 * 1024,
        },
    )
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=settings.rate_limit_per_minute,
        path_limits={"/api/compare": settings.compare_rate_limit_per_minute},
        trust_proxy=settings.trust_proxy,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    app.add_middleware(SecurityHeadersMiddleware)
    return app


async def _refresh_loop(provider: CatalogProvider) -> None:
    hours = provider.settings.refresh_hours
    while True:
        await asyncio.to_thread(provider.refresh)
        # Retry sooner while there is nothing to serve yet.
        delay = 300.0 if provider.snapshot is None else hours * 3600
        await asyncio.sleep(delay)


app = create_app()
