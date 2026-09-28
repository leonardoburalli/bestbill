"""Build ``catalog.sqlite`` + ``manifest.json`` from the ARERA source files."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from bestbill.arera import policy
from bestbill.arera.indices import parse_indices_file
from bestbill.arera.mlibero import Excluded as MliberoExcluded
from bestbill.arera.mlibero import iter_mlibero_offers
from bestbill.arera.parameters import Parameters, parse_parameters_file
from bestbill.arera.placet import Excluded as PlacetExcluded
from bestbill.arera.placet import parse_placet_file
from bestbill.core.bands import DEFAULT_HOUSEHOLD_SPLIT
from bestbill.core.calculator import estimate_annual_cost
from bestbill.core.models import (
    Band,
    ConsumptionProfile,
    MonthlyConsumption,
    Offer,
    OfferSource,
    PunSeries,
)

SCHEMA_VERSION = 2

ATTRIBUTION = (
    'Dati elaborati a partire dagli Open Data pubblicati su "Portale Offerte" '
    "(www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su "
    "disposizioni di ARERA. Licenza CC-BY 4.0."
)

_SCHEMA_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE offers (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    price_type TEXT NOT NULL,
    supplier TEXT NOT NULL,
    band_structure TEXT NOT NULL,
    customer TEXT NOT NULL,
    residency TEXT NOT NULL,
    has_geo INTEGER NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE offer_geo (
    offer_id TEXT NOT NULL REFERENCES offers(id),
    level TEXT NOT NULL,
    code TEXT NOT NULL
);
CREATE INDEX idx_offer_geo_offer_id ON offer_geo(offer_id);
CREATE INDEX idx_offer_geo_level_code ON offer_geo(level, code);

CREATE TABLE pun (
    month TEXT PRIMARY KEY,
    value REAL NOT NULL
);

CREATE TABLE excluded (
    offer_id TEXT NOT NULL,
    source TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE parameters (
    source TEXT NOT NULL,
    nome_parametro TEXT NOT NULL,
    valore REAL NOT NULL,
    descrizione TEXT NOT NULL,
    PRIMARY KEY (source, nome_parametro)
);
"""


@dataclass(frozen=True)
class BuildResult:
    sqlite_path: Path
    manifest_path: Path
    manifest: dict[str, Any]


def _reference_profile(pun: PunSeries) -> tuple[ConsumptionProfile, PunSeries]:
    """The ARERA reference domestic customer (2,700 kWh/year, standard
    band split) over the last 12 published PUN months (or a fixed
    12-month synthetic window if the series is shorter).
    """
    months_available = sorted(pun.values)
    if len(months_available) >= 12:
        months = months_available[-12:]
        reference_pun = PunSeries(values={m: pun.values[m] for m in months})
    else:
        months = [date(2024, m, 1) for m in range(1, 13)]
        reference_pun = pun

    monthly_kwh = policy.REFERENCE_CONSUMPTION_KWH / 12
    entries = [
        MonthlyConsumption(
            month=m,
            kwh=monthly_kwh,
            bands={
                Band.F1: monthly_kwh * DEFAULT_HOUSEHOLD_SPLIT[Band.F1],
                Band.F2: monthly_kwh * DEFAULT_HOUSEHOLD_SPLIT[Band.F2],
                Band.F3: monthly_kwh * DEFAULT_HOUSEHOLD_SPLIT[Band.F3],
            },
        )
        for m in months
    ]
    return ConsumptionProfile(months=entries), reference_pun


def _is_plausible(offer: Offer, profile: ConsumptionProfile, pun: PunSeries) -> bool:
    cost = estimate_annual_cost(
        offer, profile, pun, committed_power_kw=policy.REFERENCE_POWER_KW
    )
    if cost is None:
        return False
    return policy.PLAUSIBLE_MIN_EUR <= cost <= policy.PLAUSIBLE_MAX_EUR


def _dispatching_identity(params_ml: Parameters) -> dict[str, Any]:
    diff = policy.dispatching_identity_diff(params_ml)
    if diff is None:
        return {"available": False}
    ok = abs(diff) <= policy.DISPATCHING_IDENTITY_TOLERANCE
    return {"available": True, "diff": diff, "ok": ok}


def build_catalog(
    placet_path: str | Path,
    mlibero_path: str | Path,
    indices_path: str | Path,
    params_ml_path: str | Path,
    params_e_path: str | Path,
    out_dir: str | Path,
    snapshot_date: date | None = None,
) -> BuildResult:
    snapshot_date = snapshot_date if snapshot_date is not None else date.today()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = out_dir / "catalog.sqlite"
    manifest_path = out_dir / "manifest.json"

    pun = parse_indices_file(str(indices_path))
    params_ml = parse_parameters_file(str(params_ml_path))
    params_e = parse_parameters_file(str(params_e_path))

    offers: list[Offer] = []
    excluded: list[tuple[str, str, str]] = []
    seen_ids: set[str] = set()

    def _add(offer: Offer) -> None:
        if offer.id in seen_ids:
            excluded.append((offer.id, offer.source.value, "cod_offerta duplicato"))
            return
        seen_ids.add(offer.id)
        offers.append(offer)

    for placet_row in parse_placet_file(str(placet_path), params_e):
        if isinstance(placet_row, PlacetExcluded):
            excluded.append(
                (placet_row.row_id, OfferSource.PLACET.value, placet_row.reason)
            )
        else:
            _add(placet_row)

    for mlibero_row in iter_mlibero_offers(str(mlibero_path), params_ml):
        if isinstance(mlibero_row, MliberoExcluded):
            excluded.append(
                (mlibero_row.row_id, OfferSource.MLIBERO.value, mlibero_row.reason)
            )
        else:
            _add(mlibero_row)

    reference_profile, reference_pun = _reference_profile(pun)
    priced_offers: list[Offer] = []
    for offer in offers:
        if _is_plausible(offer, reference_profile, reference_pun):
            priced_offers.append(offer)
        else:
            excluded.append((offer.id, offer.source.value, "prezzo non plausibile"))

    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        for offer in priced_offers:
            conn.execute(
                "INSERT INTO offers "
                "(id, source, price_type, supplier, band_structure, customer, "
                "residency, has_geo, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    offer.id,
                    offer.source.value,
                    offer.price_type.value,
                    offer.supplier,
                    offer.band_structure.value,
                    offer.customer.value,
                    offer.residency.value,
                    1 if offer.geo is not None else 0,
                    offer.model_dump_json(),
                ),
            )
            if offer.geo is not None:
                for level, codes in (
                    ("regione", offer.geo.regioni),
                    ("provincia", offer.geo.province),
                    ("comune", offer.geo.comuni),
                ):
                    for code in codes:
                        conn.execute(
                            "INSERT INTO offer_geo (offer_id, level, code) "
                            "VALUES (?, ?, ?)",
                            (offer.id, level, code),
                        )
        for month, value in pun.values.items():
            conn.execute(
                "INSERT INTO pun (month, value) VALUES (?, ?)",
                (month.isoformat(), value),
            )
        for offer_id, source, reason in excluded:
            conn.execute(
                "INSERT INTO excluded (offer_id, source, reason) VALUES (?, ?, ?)",
                (offer_id, source, reason),
            )
        for source, params in (("mlibero", params_ml), ("placet", params_e)):
            for name, value in params.values.items():
                conn.execute(
                    "INSERT INTO parameters "
                    "(source, nome_parametro, valore, descrizione) VALUES (?, ?, ?, ?)",
                    (source, name, value, params.descriptions.get(name, "")),
                )

        counts_by_reason: dict[str, int] = {}
        for _, _, reason in excluded:
            counts_by_reason[reason] = counts_by_reason.get(reason, 0) + 1
        counts_by_source: dict[str, dict[str, int]] = {}
        for source in (OfferSource.PLACET.value, OfferSource.MLIBERO.value):
            included = sum(1 for o in priced_offers if o.source.value == source)
            excl = sum(1 for _, s, _ in excluded if s == source)
            counts_by_source[source] = {"included": included, "excluded": excl}

        meta_rows = {
            "schema_version": str(SCHEMA_VERSION),
            "snapshot_date": snapshot_date.isoformat(),
            "attribution": ATTRIBUTION,
        }
        for meta_key, meta_value in meta_rows.items():
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)", (meta_key, meta_value)
            )
        conn.commit()
    finally:
        conn.close()

    sha256 = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
    dispatching_identity = _dispatching_identity(params_ml)
    warnings: list[str] = []
    if dispatching_identity.get("available") and not dispatching_identity.get("ok"):
        warnings.append(
            "dispatching identity check failed: |Cdisp + mean(cpty_mrkt_1..3) - "
            f"cdispd| = {abs(dispatching_identity['diff']):.6f} exceeds "
            f"{policy.DISPATCHING_IDENTITY_TOLERANCE:g}"
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": snapshot_date.isoformat(),
        "sources": {
            "placet": {"path": str(placet_path)},
            "mlibero": {"path": str(mlibero_path)},
            "indices": {"path": str(indices_path)},
            "parametri_mercato_libero": {"path": str(params_ml_path)},
            "parametri_placet": {"path": str(params_e_path)},
        },
        "sqlite_sha256": sha256,
        "counts": {
            "total": len(priced_offers) + len(excluded),
            "included": len(priced_offers),
            "excluded": len(excluded),
            "excluded_by_reason": counts_by_reason,
            "by_source": counts_by_source,
        },
        "pun_months": len(pun.values),
        "dispatching_identity": dispatching_identity,
        "warnings": warnings,
        "attribution": ATTRIBUTION,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return BuildResult(
        sqlite_path=sqlite_path, manifest_path=manifest_path, manifest=manifest
    )
