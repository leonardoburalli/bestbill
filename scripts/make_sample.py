#!/usr/bin/env python
"""Generate the synthetic sample workbook used by the CLI smoke test and the
docs ("try with the sample household"). No real data: every number here is
made up.

Usage:
    uv run python scripts/make_sample.py
"""

from __future__ import annotations

import pathlib
from datetime import date

import openpyxl

OUTPUT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "bestbill"
    / "data"
    / "sample.xlsx"
)

# 12 consecutive months, Sep 2024 -> Aug 2025, ~2700 kWh/year with a
# winter/summer household shape (higher heating-adjacent consumption in
# winter months, mild dip in shoulder seasons).
MONTHS: list[tuple[int, int, float, float, float]] = [
    # (year, month, kwh, pun_eur_kwh, fc_pun_eur_kwh)
    (2024, 9, 180.0, 0.118, 0.12),
    (2024, 10, 200.0, 0.121, 0.12),
    (2024, 11, 260.0, 0.128, 0.12),
    (2024, 12, 320.0, 0.135, 0.12),
    (2025, 1, 340.0, 0.140, 0.12),
    (2025, 2, 300.0, 0.132, 0.12),
    (2025, 3, 240.0, 0.120, 0.12),
    (2025, 4, 190.0, 0.112, 0.12),
    (2025, 5, 170.0, 0.108, 0.12),
    (2025, 6, 180.0, 0.110, 0.12),
    (2025, 7, 170.0, 0.115, 0.12),
    (2025, 8, 150.0, 0.119, 0.12),
]

# Fictitious suppliers: any resemblance to real ones is coincidental.
# (name, prezzo_fisso, alpha, ccv) -- prezzo_fisso == 0 means variable (PUN + alpha).
TARIFFS: list[tuple[str, float, float, float]] = [
    ("Alfa Energia Fissa", 0.129, 0.010, 84.0),
    ("Beta Luce Variabile", 0.0, 0.018, 60.0),
    ("Gamma Power Fissa", 0.135, 0.005, 72.0),
    ("Delta Energia Variabile", 0.0, 0.022, 48.0),
    ("Epsilon Risparmio Fissa", 0.118, 0.012, 96.0),
    ("Zeta Flex Variabile", 0.0, 0.015, 90.0),
]


def build_workbook() -> openpyxl.Workbook:
    wb = openpyxl.Workbook()

    ws_tariffario = wb.active
    assert ws_tariffario is not None
    ws_tariffario.title = "Tariffario"
    ws_tariffario.append(
        ["Tariffa", "Prezzo fisso [€/kWh]", "Alpha [€/kWh]", "CCV [€]"]
    )
    for name, prezzo_fisso, alpha, ccv in TARIFFS:
        ws_tariffario.append([name, prezzo_fisso, alpha, ccv])

    ws_storico = wb.create_sheet("Storico_Esempio")
    ws_storico.append(
        ["Mese", "Consumo [kWh]", "PUN mensile [€/kWh]", "FC PUN mensile [€/kWh]"]
    )
    for year, month, kwh, pun, fc_pun in MONTHS:
        ws_storico.append([date(year, month, 1), kwh, pun, fc_pun])

    return wb


def main() -> None:
    wb = build_workbook()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
