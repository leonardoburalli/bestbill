"""Shared helpers for the API tests."""

from __future__ import annotations

from typing import Any


def compare_body(**overrides: Any) -> dict[str, Any]:
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    body: dict[str, Any] = {
        "consumption": [{"month": m, "kwh": 271.5 + i} for i, m in enumerate(months)],
    }
    body.update(overrides)
    return body
