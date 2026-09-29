#!/usr/bin/env bash
# Build and publish the ARERA catalogue from a local machine (macOS/Linux).
# ARERA's Portale Offerte answers HTTP 403 to GitHub Actions/cloud IPs, so
# this is run manually: `make catalog-publish` (needs uv and `gh auth login`).
#
# Usage: .cicd/publish-catalog.sh [--dry-run]   (or DRY_RUN=1)
# The repo comes from `gh repo view`, overridable with BESTBILL_REPO.
# Only catalog.sqlite, manifest.json and retailers.csv are uploaded; the raw
# ARERA files under build/catalog/raw are never published.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

DRY_RUN="${DRY_RUN:-0}"
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

TAG="catalog-latest"
OUT_DIR="build/catalog"
PREV_DIR="build/previous"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: the GitHub CLI (gh) is not installed; see https://cli.github.com" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh is not authenticated; run 'gh auth login' first" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to write the release notes" >&2
  exit 1
fi

REPO="${BESTBILL_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Repository: ${REPO}"
[[ "${DRY_RUN}" == "1" ]] && echo "Dry run: nothing will be published"

download_previous() {
  mkdir -p "${PREV_DIR}"
  gh release download "${TAG}" -p manifest.json -D "${PREV_DIR}" \
    --repo "${REPO}" --clobber || true
  gh release download "${TAG}" -p retailers.csv -D "${PREV_DIR}" \
    --repo "${REPO}" --clobber || true
}
step "Download the previous manifest and operators export" download_previous

PREVIOUS_MANIFEST="${PREV_DIR}/manifest.json" \
  PREVIOUS_RETAILERS="${PREV_DIR}/retailers.csv" \
  step "Fetch, build and validate the catalogue" .cicd/catalog.sh "${OUT_DIR}"

ASSETS=("${OUT_DIR}/catalog.sqlite" "${OUT_DIR}/manifest.json")
if [[ -f "${OUT_DIR}/retailers.csv" ]]; then
  ASSETS+=("${OUT_DIR}/retailers.csv")
fi

SNAPSHOT_DATE=$(jq -r '.snapshot_date' "${OUT_DIR}/manifest.json")
INCLUDED=$(jq -r '.counts.included' "${OUT_DIR}/manifest.json")
EXCLUDED=$(jq -r '.counts.excluded' "${OUT_DIR}/manifest.json")
ATTRIBUTION=$(jq -r '.attribution' "${OUT_DIR}/manifest.json")
NOTES=$(printf 'Snapshot date: %s\nOffers included: %s, excluded: %s\n\n%s\n' \
  "${SNAPSHOT_DATE}" "${INCLUDED}" "${EXCLUDED}" "${ATTRIBUTION}")

publish() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[dry-run] would create release ${TAG} on ${REPO} if missing"
    echo "[dry-run] would upload (--clobber): ${ASSETS[*]}"
    echo "[dry-run] would set release notes:"
    echo "${NOTES}"
    return 0
  fi
  if ! gh release view "${TAG}" --repo "${REPO}" >/dev/null 2>&1; then
    gh release create "${TAG}" \
      --repo "${REPO}" \
      --title "Catalogue (latest)" \
      --notes "Rolling ARERA Portale Offerte catalogue snapshot." \
      --latest=false
  fi
  gh release upload "${TAG}" "${ASSETS[@]}" --repo "${REPO}" --clobber
  gh release edit "${TAG}" --repo "${REPO}" --notes "${NOTES}"
}
step "Publish to the ${TAG} release" publish
