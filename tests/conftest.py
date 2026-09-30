import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


import pytest  # noqa: E402

FIXTURES_ARERA = PROJECT_ROOT / "fixtures" / "arera"


@pytest.fixture(scope="session")
def catalog_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """A real catalogue built once from the trimmed ARERA fixtures."""
    from bestbill.catalog.build import build_catalog

    out = tmp_path_factory.mktemp("catalog")
    build_catalog(
        placet_path=FIXTURES_ARERA / "placet.csv",
        mlibero_path=FIXTURES_ARERA / "mlibero.xml",
        indices_path=FIXTURES_ARERA / "indices.csv",
        params_ml_path=FIXTURES_ARERA / "params_ml.csv",
        params_e_path=FIXTURES_ARERA / "params_e.csv",
        operators_path=FIXTURES_ARERA / "operators.xlsx",
        out_dir=out,
    )
    return out
