import pathlib

import pytest

from bestbill.catalog.build import build_catalog
from bestbill.catalog.store import CatalogStore

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "arera"


@pytest.fixture()
def store(tmp_path):
    result = build_catalog(
        placet_path=FIXTURES / "placet.csv",
        mlibero_path=FIXTURES / "mlibero.xml",
        indices_path=FIXTURES / "indices.csv",
        params_ml_path=FIXTURES / "params_ml.csv",
        params_e_path=FIXTURES / "params_e.csv",
        out_dir=tmp_path / "catalog",
    )
    with CatalogStore(result.sqlite_path) as s:
        yield s


def test_meta_has_schema_version(store):
    meta = store.meta()
    assert meta["schema_version"] == "3"
    assert "attribution" in meta


def test_offers_returns_offer_objects(store):
    offers = store.offers(limit=5)
    assert offers
    assert all(hasattr(o, "id") for o in offers)


def test_offers_filters_by_source(store):
    offers = store.offers(source="placet", limit=100)
    assert offers
    assert all(o.source.value == "placet" for o in offers)


def test_offers_filters_by_price_type(store):
    offers = store.offers(price_type="fixed", limit=100)
    assert all(o.price_type.value == "fixed" for o in offers)


def test_pun_series_has_at_least_twelve_months(store):
    series = store.pun_series()
    assert len(series.values) >= 12


def test_eligible_offers_excludes_geo_restricted_without_comune(store):
    offers = store.eligible_offers(istat_comune=None)
    assert all(not o.geo for o in offers)


def test_eligible_offers_includes_matching_geo(store):
    all_offers = store.offers(limit=1000)
    geo_offer = next(o for o in all_offers if o.geo is not None and o.geo.comuni)
    comune = next(iter(geo_offer.geo.comuni))
    offers = store.eligible_offers(istat_comune=comune)
    assert any(o.id == geo_offer.id for o in offers)


def test_store_is_read_only(tmp_path):
    result = build_catalog(
        placet_path=FIXTURES / "placet.csv",
        mlibero_path=FIXTURES / "mlibero.xml",
        indices_path=FIXTURES / "indices.csv",
        params_ml_path=FIXTURES / "params_ml.csv",
        params_e_path=FIXTURES / "params_e.csv",
        out_dir=tmp_path / "catalog",
    )
    with CatalogStore(result.sqlite_path) as s:
        with pytest.raises(Exception):  # noqa: B017, PT011
            s._conn.execute("DELETE FROM offers")
            s._conn.commit()


def test_eligible_offers_includes_regione_restricted_offer(store):
    all_offers = store.offers(limit=1000)
    region_offer = next(
        o for o in all_offers if o.geo is not None and o.geo.regioni == {"07", "01"}
    )
    assert not any(
        o.id == region_offer.id for o in store.eligible_offers(istat_comune="015146")
    )
    for comune in ("010025", "001272"):  # Genova (07), Torino (01)
        assert any(
            o.id == region_offer.id for o in store.eligible_offers(istat_comune=comune)
        )
