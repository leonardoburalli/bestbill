"""Command-line interface: compare custom (legacy Excel) offers for a
household's consumption history. Replaces ComparazioneTariffeEE.py and
visualization.py.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
import pathlib
import sys
from collections.abc import Sequence

from bestbill.core.calculator import compare, round_eur
from bestbill.core.models import Comparison
from bestbill.io.excel import (
    ExcelFormatError,
    list_locations,
    read_custom_offers,
    read_location_data,
)

DEFAULT_INPUT_FILE = "Input/TariffeEE_Bolletta.xlsx"
DEFAULT_OUTPUT_DIR = "Output"

log = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare electricity offers for a household's 12-month history",
    )
    parser.add_argument(
        "--file", default=DEFAULT_INPUT_FILE, help="Legacy Excel workbook path"
    )
    parser.add_argument(
        "--location", required=True, help="Location (Storico_<location> sheet)"
    )
    parser.add_argument(
        "--pun",
        choices=("actual", "forecast"),
        default="actual",
        help="Which PUN series to use for variable offers",
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR, help="Where to write the CSV"
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        default=False,
        help="Also save a bar chart (requires matplotlib)",
    )
    return parser.parse_args(argv)


def _print_ranking(comparison: Comparison, location: str) -> None:
    print(f"\n=== Confronto offerte per: {location} ===\n")
    for result in comparison.results:
        cost = round_eur(result.cost_eur)
        delta = round_eur(result.delta_vs_best_eur)
        print(
            f"  {result.rank}. {result.name:35s}  {cost:10.2f} EUR/anno"
            f"  (+{delta:.2f} vs migliore)"
        )
    if comparison.excluded:
        print("\nOfferte escluse:")
        for offer_id, reason in comparison.excluded:
            print(f"  - {offer_id}: {reason}")
    print(f"\n{comparison.assumptions.statement}\n")


def _write_csv(
    comparison: Comparison, location: str, output_dir: pathlib.Path
) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.date.today().strftime('%Y%m%d')}_{location}_comparison.csv"
    output_path = output_dir / filename

    with output_path.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# {comparison.assumptions.statement}\n")
        f.write(
            f"# Periodo: {comparison.assumptions.period_start} - "
            f"{comparison.assumptions.period_end}\n"
        )
        f.write(f"# Ripartizione fasce: {comparison.assumptions.band_split_source}\n")
        if comparison.assumptions.substituted_pun_months:
            months = ", ".join(
                str(m) for m in comparison.assumptions.substituted_pun_months
            )
            f.write(f"# Mesi PUN sostituiti (dato non ancora pubblicato): {months}\n")
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "supplier",
                "name",
                "price_type",
                "cost_eur",
                "delta_vs_best_eur",
                "eur_per_kwh_effective",
                "break_even_pun_eur_kwh",
            ]
        )
        for result in comparison.results:
            writer.writerow(
                [
                    result.rank,
                    result.supplier,
                    result.name,
                    result.price_type.value,
                    round_eur(result.cost_eur),
                    round_eur(result.delta_vs_best_eur),
                    round_eur(result.eur_per_kwh_effective, 4),
                    round_eur(result.break_even_pun_eur_kwh, 4)
                    if result.break_even_pun_eur_kwh is not None
                    else "",
                ]
            )
    return output_path


def _make_chart(
    comparison: Comparison, location: str, output_dir: pathlib.Path
) -> pathlib.Path:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "The --chart option requires matplotlib. Install it with: "
            "uv sync --extra chart"
        ) from exc

    names = [r.name for r in comparison.results]
    costs = [round_eur(r.cost_eur) for r in comparison.results]

    fig, ax = plt.subplots(figsize=(max(10, len(names) * 1.5), 5))
    bars = ax.barh(names, costs, color="#4C72B0")

    for bar, cost in zip(bars, costs, strict=True):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f"EUR {cost:.2f}",
            va="center",
            ha="left",
            fontsize=9,
        )

    ax.set_xlabel("Costo annuo (EUR)")
    ax.set_title(f"Confronto offerte — {location}")
    ax.invert_yaxis()
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{location}_chart.png"
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    args = parse_args(argv)

    try:
        locations = list_locations(args.file)
    except ExcelFormatError as exc:
        log.error("Could not read %s: %s", args.file, exc)
        return 1

    if args.location not in locations:
        log.error(
            "Unknown location %r. Available locations: %s", args.location, locations
        )
        return 2

    log.info("Comparing offers for location: %s", args.location)

    try:
        profile, actual_pun, forecast_pun = read_location_data(args.file, args.location)
        offers = read_custom_offers(args.file)
    except ExcelFormatError as exc:
        log.error("Could not read %s: %s", args.file, exc)
        return 1

    pun_series = actual_pun if args.pun == "actual" else forecast_pun
    comparison = compare(offers=offers, profile=profile, pun=pun_series)

    _print_ranking(comparison, args.location)

    output_dir = pathlib.Path(args.output_dir)
    csv_path = _write_csv(comparison, args.location, output_dir)
    log.info("Results written to %s", csv_path)

    if args.chart:
        chart_path = _make_chart(comparison, args.location, output_dir)
        log.info("Chart saved to %s", chart_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
