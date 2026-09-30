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
    --params-ml tests/fixtures/arera/params_ml.csv \
    --params-e tests/fixtures/arera/params_e.csv \
    --operators tests/fixtures/arera/operators.xlsx \
    --out "${OUT_DIR}/catalog"

step "Smoke: rank catalogue-only offers for the sample household" \
  uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
    --catalog "${OUT_DIR}/catalog/catalog.sqlite" --output-dir "${OUT_DIR}"

step "Smoke: rank catalogue + custom offers (standard dispatching) together" \
  uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
    --catalog "${OUT_DIR}/catalog/catalog.sqlite" --include-custom \
    --output-dir "${OUT_DIR}"

# --- API: boot uvicorn on the fixture catalogue and run a compare ---------
API_PORT="${SMOKE_API_PORT:-8765}"
API_LOG="${OUT_DIR}/uvicorn.log"
API_PID=""
stop_api() {
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
}
trap stop_api EXIT

start_api() {
  BESTBILL_CATALOG_PATH="${OUT_DIR}/catalog/catalog.sqlite" \
    uv run uvicorn bestbill.api.main:app --host 127.0.0.1 --port "${API_PORT}" \
    >"${API_LOG}" 2>&1 &
  API_PID=$!

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "API did not become healthy; log:" >&2
  cat "${API_LOG}" >&2
  return 1
}

api_compare() {
  local base="http://127.0.0.1:${API_PORT}/api" sample body
  sample=$(curl -fsS "${base}/sample")
  body=$(python3 - "${sample}" <<'PY'
import json, sys
months = json.loads(sys.argv[1])["months"]
print(json.dumps({"consumption": [{"month": m["month"], "kwh": m["kwh"]} for m in months]}))
PY
  )
  curl -fsS -X POST "${base}/compare" -H 'content-type: application/json' \
    -d "${body}" -o "${OUT_DIR}/api_compare.json" -w 'HTTP %{http_code}\n'
  python3 - "${OUT_DIR}/api_compare.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
assert data["results"], "empty ranking"
assert data["results"][0]["rank"] == 1
assert data["assumptions"]["cost_label"].startswith("costo materia energia")
print(f"API smoke ok: {len(data['results'])} ranked offers, "
      f"best {data['results'][0]['supplier']} {data['results'][0]['cost_eur']:.2f} EUR")
PY
}

step "Smoke: start the API on the fixture catalogue" start_api
step "Smoke: POST /api/compare with the sample household" api_compare
