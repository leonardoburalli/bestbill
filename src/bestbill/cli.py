"""Command-line interface: `bestbill compare` (legacy Excel + optional
ARERA catalogue) and `bestbill catalog build|fetch`.

For backwards compatibility, invoking `bestbill` with no subcommand (i.e.
the legacy flags directly) is equivalent to `bestbill compare ...`.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
import pathlib
import sys
from collections.abc import Sequence
from datetime import date

from bestbill.arera import policy
from bestbill.arera.fetch import (
    FetchError,
    fetch_indices,
    fetch_mlibero,
    fetch_operators,
    fetch_parametri_e,
    fetch_parametri_ml,
    fetch_placet,
)
from bestbill.arera.parameters import Parameters
from bestbill.catalog.build import build_catalog
from bestbill.catalog.store import CatalogStore
from bestbill.catalog.validate import validate_catalog_dir
from bestbill.core.calculator import compare, round_eur
from bestbill.core.models import Comparison, Offer
from bestbill.io.excel import (
    ExcelFormatError,
    list_locations,
    read_custom_offers,
    read_location_data,
)

DEFAULT_INPUT_FILE = "Input/TariffeEE_Bolletta.xlsx"
DEFAULT_OUTPUT_DIR = "Output"

log = logging.getLogger(__name__)

_TOP_LEVEL_COMMANDS = ("compare", "catalog")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare electricity offers for a household's 12-month history",
    )
    subparsers = parser.add_subparsers(dest="command")

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare offers for a household (legacy Excel + optional catalogue)",
    )
    compare_parser.add_argument(
        "--file", default=DEFAULT_INPUT_FILE, help="Legacy Excel workbook path"
    )
    compare_parser.add_argument(
        "--location", required=True, help="Location (Storico_<location> sheet)"
    )
    compare_parser.add_argument(
        "--pun",
        choices=("actual", "forecast"),
        default="actual",
        help="Which PUN series to use for variable offers",
    )
    compare_parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR, help="Where to write the CSV"
    )
    compare_parser.add_argument(
        "--chart",
        action="store_true",
        default=False,
        help="Also save a bar chart (requires matplotlib)",
    )
    compare_parser.add_argument(
        "--catalog",
        default=None,
        help="Path to a catalog.sqlite; if given, ranks catalogue offers only "
        "by default (see --include-custom to also rank the workbook's offers)",
    )
    compare_parser.add_argument(
        "--include-custom",
        action="store_true",
        default=False,
        help="With --catalog, also rank the workbook's custom offers, priced "
        "with the catalogue's standard household dispatching (cdispd + "
        "dispbt_d) so they're comparable to catalogue offers (see "
        "docs/pricing-policy.md). Ignored without --catalog.",
    )
    compare_parser.add_argument(
        "--residency",
        choices=("resident", "non_resident"),
        default="resident",
        help="Used to filter residents-only/non-residents-only catalogue offers",
    )
    compare_parser.add_argument(
        "--istat-comune",
        default=None,
        help="6-digit ISTAT comune code; required to include geo-restricted "
        "catalogue offers",
    )
    compare_parser.add_argument(
        "--committed-power-kw",
        type=float,
        default=3.0,
        help="Committed power, used to price €/kW/year power fees",
    )

    catalog_parser = subparsers.add_parser(
        "catalog", help="Build/fetch the ARERA catalogue"
    )
    catalog_subparsers = catalog_parser.add_subparsers(dest="catalog_command")

    build_parser = catalog_subparsers.add_parser(
        "build", help="Build catalog.sqlite + manifest.json from ARERA source files"
    )
    build_parser.add_argument("--placet", required=True, help="PLACET EE CSV path")
    build_parser.add_argument(
        "--mlibero", required=True, help="Mercato libero EE XML path"
    )
    build_parser.add_argument(
        "--indices", required=True, help="Historical indices CSV path"
    )
    build_parser.add_argument(
        "--params-ml",
        required=True,
        help="Mercato libero dispatching parameters CSV path "
        "(PO_Parametri_Mercato_Libero_E_*.csv)",
    )
    build_parser.add_argument(
        "--params-e",
        required=True,
        help="PLACET dispatching parameters CSV path (PO_Parametri_E_*.csv)",
    )
    build_parser.add_argument("--out", required=True, help="Output directory")
    build_parser.add_argument(
        "--operators",
        default=None,
        help="ARERA 'Ricerca operatori' export (.zip or .xlsx), optional; used "
        "to name mercato libero offers by retailer instead of their VAT",
    )
    build_parser.add_argument(
        "--previous-manifest",
        default=None,
        help="Previous manifest.json, for the count gate",
    )
    build_parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date (YYYY-MM-DD); defaults to today",
    )

    fetch_parser = catalog_subparsers.add_parser(
        "fetch", help="Download the day's ARERA source files"
    )
    fetch_parser.add_argument("--date", required=True, help="Target date (YYYY-MM-DD)")
    fetch_parser.add_argument("--out", required=True, help="Output directory")

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list or args_list[0] not in (*_TOP_LEVEL_COMMANDS, "-h", "--help"):
        args_list = ["compare", *args_list]
    return _build_parser().parse_args(args_list)


def _print_ranking(comparison: Comparison, location: str) -> None:
    print(f"\n=== Confronto offerte per: {location} ===\n")
    print(
        "Costo stimato: sola quota energia e fornitura (il costo che varia da "
        "fornitore a fornitore). Non include costi di rete, oneri di sistema, "
        "accise e IVA, uguali per ogni fornitore e quindi esclusi dal confronto.\n"
    )
    for result in comparison.results:
        cost = round_eur(result.cost_eur)
        delta = round_eur(result.delta_vs_best_eur)
        print(
            f"  {result.rank}. {result.name:35s}  {cost:10.2f} EUR/anno (fornitore)"
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
            "# Costo stimato: sola quota energia e fornitura (non include costi di "
            "rete, oneri di sistema, accise e IVA, uguali per ogni fornitore)\n"
        )
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
                "supplier_cost_eur",
                "delta_vs_best_eur",
                "supplier_eur_per_kwh_effective",
                "break_even_pun_eur_kwh",
                "break_even_status",
                "standard_dispatching_estimate",
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
                    result.break_even_status.value
                    if result.break_even_status is not None
                    else "",
                    "yes" if result.dispatching_is_standard_estimate else "",
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


def _catalog_offers(
    catalog_path: str, istat_comune: str | None, residency: str
) -> list[Offer]:
    with CatalogStore(catalog_path) as store:
        return store.eligible_offers(istat_comune=istat_comune, residency=residency)  # type: ignore[arg-type]


def _with_standard_household_dispatching(
    offers: list[Offer], catalog_path: str
) -> list[Offer]:
    """Price custom (legacy Excel) offers with the catalogue's standard
    household dispatching (``cdispd`` €/kWh + ``dispbt_d`` €/year, from the
    PLACET parameters table) so they're comparable to catalogue offers
    instead of unfairly cheaper for lacking dispatching entirely (see
    ``--include-custom``, docs/pricing-policy.md).
    """
    with CatalogStore(catalog_path) as store:
        values = store.parameters("placet")
    result, reason = policy.placet_domestic_dispatching(Parameters(values=values))
    if result is None:
        log.warning(
            "Could not price custom offers with standard household "
            "dispatching (%s); showing them without dispatching",
            reason,
        )
        return offers
    return [
        offer.model_copy(
            update={
                "dispatching_eur_kwh": result.eur_kwh,
                "dispatching_eur_year": result.eur_year,
                "dispatching_breakdown": result.breakdown,
                "dispatching_is_standard_estimate": True,
            }
        )
        for offer in offers
    ]


def _run_compare(args: argparse.Namespace) -> int:
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

    if args.catalog:
        catalog_offers = _catalog_offers(
            args.catalog, args.istat_comune, args.residency
        )
        if args.include_custom:
            offers = [
                *_with_standard_household_dispatching(offers, args.catalog),
                *catalog_offers,
            ]
            log.info(
                "Loaded %d offers from catalogue %s (plus %d custom offers, "
                "priced with the standard household dispatching)",
                len(catalog_offers),
                args.catalog,
                len(offers) - len(catalog_offers),
            )
        else:
            offers = catalog_offers
            log.info(
                "Loaded %d offers from catalogue %s (custom offers excluded; "
                "use --include-custom to add them)",
                len(catalog_offers),
                args.catalog,
            )

    comparison = compare(
        offers=offers,
        profile=profile,
        pun=pun_series,
        residency=args.residency,
        istat_comune=args.istat_comune,
        committed_power_kw=args.committed_power_kw,
    )

    _print_ranking(comparison, args.location)

    output_dir = pathlib.Path(args.output_dir)
    csv_path = _write_csv(comparison, args.location, output_dir)
    log.info("Results written to %s", csv_path)

    if args.chart:
        chart_path = _make_chart(comparison, args.location, output_dir)
        log.info("Chart saved to %s", chart_path)

    return 0


def _run_catalog_build(args: argparse.Namespace) -> int:
    snapshot_date = (
        date.fromisoformat(args.snapshot_date) if args.snapshot_date else None
    )
    result = build_catalog(
        placet_path=args.placet,
        mlibero_path=args.mlibero,
        indices_path=args.indices,
        params_ml_path=args.params_ml,
        params_e_path=args.params_e,
        out_dir=args.out,
        snapshot_date=snapshot_date,
        operators_path=args.operators,
    )
    log.info(
        "Built %s: %d offers included, %d excluded",
        result.sqlite_path,
        result.manifest["counts"]["included"],
        result.manifest["counts"]["excluded"],
    )
    validation = validate_catalog_dir(
        args.out, previous_manifest_path=args.previous_manifest
    )
    if not validation.ok:
        for error in validation.errors:
            log.error("Validation error: %s", error)
        return 1
    log.info("Catalogue validation passed")
    return 0


def _run_catalog_fetch(args: argparse.Namespace) -> int:
    target = date.fromisoformat(args.date)
    out_dir = pathlib.Path(args.out)
    placet_result = fetch_placet(target, out_dir / "PO_Offerte_E_PLACET.csv")
    mlibero_result = fetch_mlibero(target, out_dir / "PO_Offerte_E_MLIBERO.xml")
    fetch_parametri_ml(target, out_dir / "PO_Parametri_Mercato_Libero_E.csv")
    fetch_parametri_e(target, out_dir / "PO_Parametri_E.csv")
    fetch_indices(out_dir / "indices.csv")
    try:
        fetch_operators(out_dir / "operators.zip")
    except FetchError as exc:
        # Soft failure: the operator list is optional (--operators on
        # `catalog build`); .cicd/catalog.sh falls back to the previous
        # snapshot's cached export, then to no operators at all.
        log.warning("Could not fetch the ARERA operators export: %s", exc)
    log.info(
        "Fetched PLACET (effective %s) and mercato libero (effective %s) into %s",
        placet_result.effective_date,
        mlibero_result.effective_date,
        out_dir,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    args = parse_args(argv)

    if args.command == "catalog":
        if args.catalog_command == "build":
            return _run_catalog_build(args)
        if args.catalog_command == "fetch":
            return _run_catalog_fetch(args)
        log.error("Unknown catalog command; use 'build' or 'fetch'")
        return 2

    return _run_compare(args)


if __name__ == "__main__":
    sys.exit(main())
