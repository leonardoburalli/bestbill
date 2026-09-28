#!/usr/bin/env bash
# End-to-end smoke test: run the CLI on the synthetic sample file.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

step "Smoke: compare offers for the sample household" \
  uv run bestbill --file src/bestbill/data/sample.xlsx --location Esempio \
    --output-dir "${1:-build/smoke}"
