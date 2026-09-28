"""Read-only query layer over ``catalog.sqlite``."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from bestbill.core.models import Offer, PunSeries


class CatalogStore:
    """Opens ``catalog.sqlite`` read-only (``mode=ro``); never writes."""

    def __init__(self, sqlite_path: str | Path):
        self._path = Path(sqlite_path)
        self._conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CatalogStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def meta(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM meta").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def offers(
        self,
        *,
        source: str | None = None,
        price_type: str | None = None,
        supplier: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Offer]:
        clauses: list[str] = []
        params: list[str] = []
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if price_type is not None:
            clauses.append("price_type = ?")
            params.append(price_type)
        if supplier is not None:
            clauses.append("supplier = ?")
            params.append(supplier)
        if q is not None:
            clauses.append("(supplier LIKE ? OR data LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT data FROM offers {where} ORDER BY id LIMIT ? OFFSET ?"  # noqa: S608
        rows = self._conn.execute(sql, (*params, limit, offset)).fetchall()
        return [Offer.model_validate_json(r["data"]) for r in rows]

    def offer_ids_in_geo(
        self, level: Literal["regione", "provincia", "comune"], code: str
    ) -> set[str]:
        rows = self._conn.execute(
            "SELECT offer_id FROM offer_geo WHERE level = ? AND code = ?", (level, code)
        ).fetchall()
        return {r["offer_id"] for r in rows}

    def eligible_offers(
        self,
        *,
        customer: str = "domestic",
        residency: Literal["resident", "non_resident"] = "resident",
        istat_comune: str | None = None,
    ) -> list[Offer]:
        """National offers, plus geo-restricted offers matching
        ``istat_comune`` (province derived from its first 3 digits, see
        ``GeoRestriction.matches``); residency filtering is left to
        ``bestbill.core.calculator.compare`` (this is a coarse
        pre-filter to avoid loading every row).
        """
        rows = self._conn.execute(
            "SELECT data FROM offers WHERE customer = ? AND has_geo = 0", (customer,)
        ).fetchall()
        offers = [Offer.model_validate_json(r["data"]) for r in rows]
        if istat_comune is not None:
            provincia = istat_comune[:3]
            geo_rows = self._conn.execute(
                "SELECT DISTINCT offer_id FROM offer_geo WHERE "
                "(level = 'comune' AND code = ?) OR (level = 'provincia' AND code = ?)",
                (istat_comune, provincia),
            ).fetchall()
            geo_ids = [r["offer_id"] for r in geo_rows]
            if geo_ids:
                placeholders = ",".join("?" * len(geo_ids))
                geo_data_rows = self._conn.execute(
                    f"SELECT data FROM offers WHERE id IN ({placeholders})",  # noqa: S608
                    geo_ids,
                ).fetchall()
                offers.extend(
                    Offer.model_validate_json(r["data"]) for r in geo_data_rows
                )
        del residency  # eligibility on residency is handled by compare()
        return offers

    def pun_series(self) -> PunSeries:
        rows = self._conn.execute("SELECT month, value FROM pun").fetchall()
        return PunSeries(
            values={date.fromisoformat(r["month"]): r["value"] for r in rows}
        )

    def suppliers(self) -> Sequence[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT supplier FROM offers ORDER BY supplier"
        ).fetchall()
        return [r["supplier"] for r in rows]
