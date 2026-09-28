"""Validation gates for a built catalogue: schema checks, minimum content,
and (optionally) a sanity comparison against the previous day's manifest.

Pricing-sanity exclusion ("prezzo non plausibile") already happens in
``build.py`` (offers, not the whole build, are excluded); this module only
gates the build as a whole (pass/fail).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bestbill.arera import policy

_REQUIRED_TABLES = {"meta", "offers", "offer_geo", "pun", "excluded", "parameters"}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def validate_catalog(
    sqlite_path: str | Path,
    manifest: dict[str, Any],
    previous_manifest: dict[str, Any] | None = None,
    count_tolerance: float = policy.COUNT_CHANGE_TOLERANCE,
) -> ValidationResult:
    errors: list[str] = []
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        tables = _table_names(conn)
        missing = _REQUIRED_TABLES - tables
        if missing:
            errors.append(f"missing table(s): {sorted(missing)}")
        else:
            for source in ("placet", "mlibero"):
                (count,) = conn.execute(
                    "SELECT COUNT(*) FROM offers WHERE source = ?", (source,)
                ).fetchone()
                if count < 1:
                    errors.append(f"no offers from source {source!r}")

            (pun_count,) = conn.execute("SELECT COUNT(*) FROM pun").fetchone()
            if pun_count < 12:
                errors.append(
                    f"PUN series has only {pun_count} month(s), expected >= 12"
                )
    finally:
        conn.close()

    if manifest.get("schema_version") is None:
        errors.append("manifest missing schema_version")
    if not manifest.get("attribution"):
        errors.append("manifest missing attribution text")

    if previous_manifest is not None:
        prev_included = previous_manifest.get("counts", {}).get("included")
        curr_included = manifest.get("counts", {}).get("included")
        if prev_included and curr_included is not None:
            lower = prev_included * (1 - count_tolerance)
            upper = prev_included * (1 + count_tolerance)
            if not (lower <= curr_included <= upper):
                errors.append(
                    f"included-offer count {curr_included} is outside "
                    f"±{count_tolerance:.0%} of the previous snapshot's "
                    f"{prev_included} ([{lower:.0f}, {upper:.0f}])"
                )

    return ValidationResult(ok=not errors, errors=errors)


def validate_catalog_dir(
    catalog_dir: str | Path,
    previous_manifest_path: str | Path | None = None,
    count_tolerance: float = policy.COUNT_CHANGE_TOLERANCE,
) -> ValidationResult:
    catalog_dir = Path(catalog_dir)
    manifest = json.loads((catalog_dir / "manifest.json").read_text(encoding="utf-8"))
    previous_manifest = None
    if previous_manifest_path is not None and Path(previous_manifest_path).exists():
        previous_manifest = json.loads(
            Path(previous_manifest_path).read_text(encoding="utf-8")
        )
    return validate_catalog(
        catalog_dir / "catalog.sqlite",
        manifest,
        previous_manifest=previous_manifest,
        count_tolerance=count_tolerance,
    )
