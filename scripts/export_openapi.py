"""Write the API's OpenAPI schema to ``openapi.json`` at the repo root.

The frontend generates its types from this file. ``make openapi`` refreshes
it; ``tests/test_openapi.py`` fails when it is out of date.
"""

from __future__ import annotations

import json
from pathlib import Path

from bestbill.api.main import create_app
from bestbill.api.settings import Settings

OUT = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    schema = create_app(Settings()).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
