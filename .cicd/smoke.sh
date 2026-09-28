#!/usr/bin/env bash
# End-to-end smoke test: run the CLI on the synthetic sample file, then
# build a small catalogue from the trimmed ARERA fixtures and rank real
# offers for the same sample household.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

OUT_DIR="${1:-build/smoke}"

step "Smoke: compare custom offers for the sample household" \
  uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
    --output-dir "${OUT_DIR}"

step "Smoke: build a catalogue from the ARERA fixtures" \
  uv run bestbill catalog build \
    --placet tests/fixtures/arera/placet.csv \
    --mlibero tests/fixtures/arera/mlibero.xml \
    --indices tests/fixtures/arera/indices.csv \
    --out "${OUT_DIR}/catalog"

step "Smoke: rank real (fixture) offers for the sample household" \
  uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
    --catalog "${OUT_DIR}/catalog/catalog.sqlite" --output-dir "${OUT_DIR}"
