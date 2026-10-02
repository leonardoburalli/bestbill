import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _script():
    spec = importlib.util.spec_from_file_location(
        "export_openapi", ROOT / "scripts" / "export_openapi.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_json_is_up_to_date():
    committed = (ROOT / "openapi.json").read_text(encoding="utf-8")
    assert committed == _script().render(), (
        "openapi.json is stale (also after every version bump): "
        "run `make openapi` and commit"
    )
