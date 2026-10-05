"""Command-line interface: `bestbill catalog build|fetch`."""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from collections.abc import Sequence
from datetime import date

from bestbill.arera.fetch import (
    FetchError,
    fetch_indices,
    fetch_mlibero,
    fetch_operators,
    fetch_parametri_e,
    fetch_parametri_ml,
    fetch_placet,
)
from bestbill.catalog.build import build_catalog
from bestbill.catalog.validate import validate_catalog_dir

log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BestBill catalogue tools",
    )
    subparsers = parser.add_subparsers(dest="command")

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
        help="ARERA 'Ricerca operatori' export (.zip, .xlsx, or the "
        "minimised retailers.csv this pipeline publishes), optional; used "
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
    return _build_parser().parse_args(args_list)


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
    if result.discount_review_path is not None:
        log.info(
            "Discount review list (local only, not published): %d rows -> %s",
            result.discount_review_count,
            result.discount_review_path,
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

    _build_parser().print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
