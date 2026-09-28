#!/usr/bin/env bash
# Daily data pipeline: fetch ARERA source files -> build catalog.sqlite ->
# validate. Set PREVIOUS_MANIFEST to a manifest.json path to enable the
# count-change gate against the last published snapshot. Set
# PREVIOUS_OPERATORS to a cached operators.zip to fall back to it if
# today's ARERA "Ricerca operatori" fetch fails (see
# bestbill.arera.fetch.fetch_operators).
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

OUT_DIR="${1:-build/catalog}"
RAW_DIR="${OUT_DIR}/raw"
DATE="${SNAPSHOT_DATE:-$(date -u +%Y-%m-%d)}"

step "Fetch ARERA source files" \
  uv run bestbill catalog fetch --date "${DATE}" --out "${RAW_DIR}"

if [[ ! -f "${RAW_DIR}/operators.zip" && -n "${PREVIOUS_OPERATORS:-}" \
      && -f "${PREVIOUS_OPERATORS}" ]]; then
  echo "Falling back to the previous snapshot's cached operators export"
  cp "${PREVIOUS_OPERATORS}" "${RAW_DIR}/operators.zip"
fi

BUILD_ARGS=(
  --placet "${RAW_DIR}/PO_Offerte_E_PLACET.csv"
  --mlibero "${RAW_DIR}/PO_Offerte_E_MLIBERO.xml"
  --indices "${RAW_DIR}/indices.csv"
  --params-ml "${RAW_DIR}/PO_Parametri_Mercato_Libero_E.csv"
  --params-e "${RAW_DIR}/PO_Parametri_E.csv"
  --out "${OUT_DIR}"
)
if [[ -n "${PREVIOUS_MANIFEST:-}" && -f "${PREVIOUS_MANIFEST}" ]]; then
  BUILD_ARGS+=(--previous-manifest "${PREVIOUS_MANIFEST}")
fi
if [[ -f "${RAW_DIR}/operators.zip" ]]; then
  BUILD_ARGS+=(--operators "${RAW_DIR}/operators.zip")
fi

step "Build and validate the catalogue" \
  uv run bestbill catalog build "${BUILD_ARGS[@]}"

if [[ -f "${RAW_DIR}/operators.zip" ]]; then
  cp "${RAW_DIR}/operators.zip" "${OUT_DIR}/operators.zip"
fi
