"""Shared helpers for the API tests."""

from __future__ import annotations

import io
from typing import Any

import openpyxl


def compare_body(**overrides: Any) -> dict[str, Any]:
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    body: dict[str, Any] = {
        "consumption": [{"month": m, "kwh": 271.5 + i} for i, m in enumerate(months)],
    }
    body.update(overrides)
    return body


def xlsx_bytes(location: str = "Casa", kwh: float = 300.0, months: int = 12) -> bytes:
    from datetime import date

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = f"Storico_{location}"
    ws.append(
        ["Mese", "Consumo [kWh]", "PUN mensile [€/kWh]", "FC PUN mensile [€/kWh]"]
    )
    for i in range(months):
        ws.append([date(2025, i + 1, 1), kwh + i, 0.11, 0.12])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
