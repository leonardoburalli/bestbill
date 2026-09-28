import json
import pathlib
import shutil
import sqlite3

import pytest

from bestbill.catalog.build import build_catalog
from bestbill.catalog.validate import validate_catalog_dir

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "arera"


@pytest.fixture()
def built_catalog(tmp_path):
    return build_catalog(
        placet_path=FIXTURES / "placet.csv",
        mlibero_path=FIXTURES / "mlibero.xml",
        indices_path=FIXTURES / "indices.csv",
        params_ml_path=FIXTURES / "params_ml.csv",
        params_e_path=FIXTURES / "params_e.csv",
        out_dir=tmp_path / "catalog",
    )


def test_build_catalog_creates_sqlite_and_manifest(built_catalog):
    assert built_catalog.sqlite_path.exists()
    assert built_catalog.manifest_path.exists()
    manifest = json.loads(built_catalog.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["attribution"]
    assert manifest["counts"]["included"] > 0


def test_build_catalog_has_both_sources(built_catalog):
    counts = built_catalog.manifest["counts"]["by_source"]
    assert counts["placet"]["included"] > 0
    assert counts["mlibero"]["included"] > 0


def test_build_catalog_pun_series_present(built_catalog):
    assert built_catalog.manifest["pun_months"] >= 12


def test_validate_passes_on_fresh_build(built_catalog):
    result = validate_catalog_dir(built_catalog.sqlite_path.parent)
    assert result.ok, result.errors


def test_validate_fails_on_missing_table(tmp_path, built_catalog):
    catalog_dir = tmp_path / "broken"
    shutil.copytree(built_catalog.sqlite_path.parent, catalog_dir)
    conn = sqlite3.connect(catalog_dir / "catalog.sqlite")
    conn.execute("DROP TABLE pun")
    conn.commit()
    conn.close()
    result = validate_catalog_dir(catalog_dir)
    assert not result.ok
    assert any("missing table" in e for e in result.errors)


def test_validate_count_gate_within_tolerance(built_catalog, tmp_path):
    previous = dict(built_catalog.manifest)
    previous["counts"] = dict(previous["counts"])
    previous["counts"]["included"] = built_catalog.manifest["counts"]["included"]
    prev_path = tmp_path / "previous_manifest.json"
    prev_path.write_text(json.dumps(previous), encoding="utf-8")

    result = validate_catalog_dir(
        built_catalog.sqlite_path.parent, previous_manifest_path=prev_path
    )
    assert result.ok, result.errors


def test_validate_count_gate_fails_outside_tolerance(built_catalog, tmp_path):
    previous = dict(built_catalog.manifest)
    previous["counts"] = dict(previous["counts"])
    previous["counts"]["included"] = built_catalog.manifest["counts"]["included"] * 10
    prev_path = tmp_path / "previous_manifest.json"
    prev_path.write_text(json.dumps(previous), encoding="utf-8")

    result = validate_catalog_dir(
        built_catalog.sqlite_path.parent, previous_manifest_path=prev_path
    )
    assert not result.ok
    assert any("±" in e for e in result.errors)


def test_build_catalog_excludes_implausible_offers_without_failing(built_catalog):
    manifest = built_catalog.manifest
    # The gate should never crash the build; it only redistributes offers
    # between "included" and "excluded".
    assert manifest["counts"]["total"] == (
        manifest["counts"]["included"] + manifest["counts"]["excluded"]
    )


def test_build_catalog_dispatching_identity_check_passes_on_fixture_params(
    built_catalog,
):
    identity = built_catalog.manifest["dispatching_identity"]
    assert identity["available"]
    assert identity["ok"]
    assert built_catalog.manifest["warnings"] == []


def test_build_catalog_parameters_table_is_populated(built_catalog):
    conn = sqlite3.connect(f"file:{built_catalog.sqlite_path}?mode=ro", uri=True)
    try:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM parameters WHERE source = 'mlibero'"
        ).fetchone()
        assert count > 0
    finally:
        conn.close()


@pytest.fixture()
def built_catalog_with_operators(tmp_path):
    return build_catalog(
        placet_path=FIXTURES / "placet.csv",
        mlibero_path=FIXTURES / "mlibero.xml",
        indices_path=FIXTURES / "indices.csv",
        params_ml_path=FIXTURES / "params_ml.csv",
        params_e_path=FIXTURES / "params_e.csv",
        operators_path=FIXTURES / "operators.xlsx",
        out_dir=tmp_path / "catalog",
    )


def test_build_catalog_manifest_has_licence_and_sources(built_catalog):
    manifest = built_catalog.manifest
    assert manifest["licence"] == "CC-BY-SA-4.0"
    assert isinstance(manifest["sources"], list)
    names = {s["name"] for s in manifest["sources"]}
    assert "ARERA – Ricerca operatori" in names
    for source in manifest["sources"]:
        assert source["licence"] in ("CC-BY-SA-4.0", "CC-BY-4.0")


def test_build_catalog_manifest_has_supplier_names_counts(built_catalog):
    counts = built_catalog.manifest["supplier_names"]
    assert set(counts) == {"arera", "placet", "domain", "vat"}
    assert sum(counts.values()) > 0


def test_build_catalog_resolves_supplier_name_from_operators_export(
    built_catalog_with_operators,
):
    from bestbill.catalog.store import CatalogStore

    with CatalogStore(built_catalog_with_operators.sqlite_path) as store:
        offers = store.offers(source="mlibero", limit=1000)
    by_id = {o.id: o for o in offers}
    offer = by_id["028269ESVML01XXCASALUCE260821001"]
    assert offer.supplier == "100ENERGIA S.R.L."
    assert offer.supplier_vat == "08985501215"
    assert offer.supplier_name_source == "arera"


def test_build_catalog_publishes_minimised_retailers_csv(
    built_catalog_with_operators,
):
    import csv

    csv_path = built_catalog_with_operators.operators_csv_path
    assert csv_path is not None
    assert csv_path == built_catalog_with_operators.sqlite_path.parent / "retailers.csv"
    assert csv_path.exists()

    with csv_path.open(encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert tuple(header) == ("partita_iva", "ragione_sociale", "sito_web")

    manifest = built_catalog_with_operators.manifest
    assert "retailers.csv" in manifest["files"]
    arera_source = next(
        s for s in manifest["sources"] if s["name"] == "ARERA – Ricerca operatori"
    )
    assert arera_source["file"] == "retailers.csv"


def test_build_catalog_output_dir_has_no_raw_operators_export(
    built_catalog_with_operators, built_catalog
):
    for result in (built_catalog_with_operators, built_catalog):
        out_dir = result.sqlite_path.parent
        raw_files = [
            p for p in out_dir.iterdir() if p.suffix.lower() in (".zip", ".xlsx")
        ]
        assert raw_files == []
