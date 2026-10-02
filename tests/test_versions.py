import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_frontend_version_matches_pyproject():
    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    js = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    assert js == py, f"frontend/package.json ({js}) != pyproject.toml ({py}): bump both"
    assert re.fullmatch(r"\d+\.\d+\.\d+", py)
