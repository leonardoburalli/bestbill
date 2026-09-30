"""API configuration, read from the environment (see README)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from bestbill.api.catalog_source import CatalogSettings

STALE_AFTER_DAYS = 3


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    catalog: CatalogSettings = field(default_factory=CatalogSettings)
    trust_proxy: bool = False
    cors_origins: tuple[str, ...] = ()
    rate_limit_per_minute: int = 60
    compare_rate_limit_per_minute: int = 20
    max_compare_body_bytes: int = 64 * 1024
    max_upload_bytes: int = 2 * 1024 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        origins = tuple(
            o.strip()
            for o in e.get("BESTBILL_CORS_ORIGINS", "").split(",")
            if o.strip()
        )
        return cls(
            catalog=CatalogSettings.from_env(e),
            trust_proxy=_truthy(e.get("BESTBILL_TRUST_PROXY")),
            cors_origins=origins,
        )
