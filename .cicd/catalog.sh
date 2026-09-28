#!/usr/bin/env bash
# Daily data pipeline: fetch ARERA source files -> build catalog.sqlite ->
# validate. Set PREVIOUS_MANIFEST to a manifest.json path to enable the
# count-change gate against the last published snapshot. Set
# PREVIOUS_RETAILERS to a cached, minimised retailers.csv
# (build/previous/retailers.csv) to fall back to it if today's ARERA
# "Ricerca operatori" fetch fails (see bestbill.arera.fetch.fetch_operators).
#
# Data minimisation (see PROVENANCE.md): the raw ARERA export (zip/xlsx)
# carries addresses and customer contacts and is only ever kept under
# ${RAW_DIR}, which is never copied to ${OUT_DIR} or published. The build
# writes a minimised retailers.csv (partita_iva/ragione_sociale/sito_web
# only) into ${OUT_DIR}; that's what gets published/cached instead.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

OUT_DIR="${1:-build/catalog}"
RAW_DIR="${OUT_DIR}/raw"
DATE="${SNAPSHOT_DATE:-$(date -u +%Y-%m-%d)}"

step "Fetch ARERA source files" \
  uv run bestbill catalog fetch --date "${DATE}" --out "${RAW_DIR}"

OPERATORS_ARG=""
if [[ -f "${RAW_DIR}/operators.zip" ]]; then
  OPERATORS_ARG="${RAW_DIR}/operators.zip"
elif [[ -n "${PREVIOUS_RETAILERS:-}" && -f "${PREVIOUS_RETAILERS}" ]]; then
  echo "Falling back to the previous snapshot's cached operators export"
  OPERATORS_ARG="${PREVIOUS_RETAILERS}"
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
if [[ -n "${OPERATORS_ARG}" ]]; then
  BUILD_ARGS+=(--operators "${OPERATORS_ARG}")
fi

step "Build and validate the catalogue" \
  uv run bestbill catalog build "${BUILD_ARGS[@]}"
