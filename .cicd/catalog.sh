#!/usr/bin/env bash
# Daily data pipeline: fetch ARERA source files -> build catalog.sqlite ->
# validate. Set PREVIOUS_MANIFEST to a manifest.json path to enable the
# count-change gate against the last published snapshot.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

OUT_DIR="${1:-build/catalog}"
RAW_DIR="${OUT_DIR}/raw"
DATE="${SNAPSHOT_DATE:-$(date -u +%Y-%m-%d)}"

step "Fetch ARERA source files" \
  uv run bestbill catalog fetch --date "${DATE}" --out "${RAW_DIR}"

BUILD_ARGS=(
  --placet "${RAW_DIR}/PO_Offerte_E_PLACET.csv"
  --mlibero "${RAW_DIR}/PO_Offerte_E_MLIBERO.xml"
  --indices "${RAW_DIR}/indices.csv"
  --out "${OUT_DIR}"
)
if [[ -n "${PREVIOUS_MANIFEST:-}" && -f "${PREVIOUS_MANIFEST}" ]]; then
  BUILD_ARGS+=(--previous-manifest "${PREVIOUS_MANIFEST}")
fi

step "Build and validate the catalogue" \
  uv run bestbill catalog build "${BUILD_ARGS[@]}"
