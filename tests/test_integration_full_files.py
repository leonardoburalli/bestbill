"""Local-only integration test: builds the catalogue from the full, real
ARERA source files if present, printing counts. Skipped by default
(``-m "not slow"`` in pyproject.toml); run explicitly with
``uv run pytest -m slow tests/test_integration_full_files.py``.

Point ``BESTBILL_ARERA_FIXTURES_DIR`` at a directory containing
``e_placet.csv``, ``e_ml.xml`` and ``idx.csv`` (the real, un-trimmed
files) to run it.
"""

from __future__ import annotations

import os
import pathlib

import pytest

pytestmark = pytest.mark.slow


def _full_files_dir() -> pathlib.Path | None:
    env_dir = os.environ.get("BESTBILL_ARERA_FIXTURES_DIR")
    if env_dir:
        candidate = pathlib.Path(env_dir)
        if (candidate / "e_placet.csv").exists():
            return candidate
    return None


def test_build_catalog_from_full_real_files(tmp_path):
    directory = _full_files_dir()
    if directory is None:
        pytest.skip("BESTBILL_ARERA_FIXTURES_DIR not set or missing e_placet.csv")

    from bestbill.catalog.build import build_catalog

    result = build_catalog(
        placet_path=directory / "e_placet.csv",
        mlibero_path=directory / "e_ml.xml",
        indices_path=directory / "idx.csv",
        params_ml_path=directory / "par_ml.csv",
        params_e_path=directory / "par_e.csv",
        out_dir=tmp_path / "catalog",
    )
    counts = result.manifest["counts"]
    print(f"\nFull-file build counts: {counts}")
    print(f"Dispatching identity: {result.manifest['dispatching_identity']}")
    print(f"Warnings: {result.manifest['warnings']}")
    assert counts["included"] > 0
