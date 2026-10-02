# BestBill

Which electricity offer is cheapest for **your own** consumption? BestBill is a
free, open-source tool for Italian households: enter 12 months of kWh, get a
ranked list of offers with a clear breakdown of the assumptions behind the
estimate — no sign-up, no personal data stored.

> Status: core engine + CLI + ARERA catalogue importer + stateless API
> (Phase 0–3 of `PLAN.md`). The React frontend is coming next; see
> `PLAN.md` for the full roadmap.

## Scope: what this compares

Every estimate is the **commodity/supplier cost only, before VAT**
("costo materia energia (IVA esclusa)"): energy price or spread over the
PUN index (with network losses applied where flagged), supplier fixed
fees, supplier-set €/kWh extras, dispatching (TIPO_DISPACCIAMENTO,
priced from the ARERA parameters files), power fees, one-off fees, and
unconditional discounts — the part of the bill that varies from supplier
to supplier.

Network charges, system charges, excise duties and VAT are **never**
added: they're set by regulation, identical for every supplier, and
therefore irrelevant to *which offer is cheapest* (and don't depend on
which retailer you pick). Results are labelled "stima" of the
supplier/commodity cost, never as the full electricity bill, and there is
no full-bill calculation anywhere in this codebase. Offers referencing
**Maggior Tutela** (closed to new customers) are excluded and counted; see
`docs/pricing-policy.md` and `docs/arera-data.md` for the full ruleset.

## What it does today

- A pure, typed calculation engine (`bestbill.core`): given a 12-month
  consumption profile, a set of offers and a PUN (national single price)
  series, it ranks offers by estimated annual cost, with per-offer
  break-even PUN for variable offers, network losses, dispatching extras,
  power fees, unconditional discounts, and residency/geographic
  eligibility.
- A daily ARERA *Portale Offerte* importer (`bestbill.arera`): PLACET CSV
  and mercato libero XML parsers (streaming, real fixtures), a PUN indices
  parser, and a fetcher with retry/fallback — every uncertain pricing rule
  lives in one place, `bestbill.arera.policy`.
- A read-only offers catalogue (`bestbill.catalog`): `catalog build` writes
  a validated `catalog.sqlite` + `manifest.json` snapshot; `catalog fetch`
  downloads the day's source files.
- A stateless HTTP API (`bestbill.api`, FastAPI): compare, offers browse,
  comune autocomplete, sample household, catalogue meta.
- Area-restricted offers are matched by comune, provincia and regione using
  the ISTAT comuni table (`bestbill.geo`).
- A CLI (`bestbill`) with `catalog build|fetch` subcommands.

## Quick start

```bash
# Install the locked environment (uv: https://docs.astral.sh/uv/)
make install

# Build a catalogue from ARERA source files (or `bestbill catalog fetch` them)
uv run bestbill catalog build --placet PO_Offerte_E_PLACET.csv \
  --mlibero PO_Offerte_E_MLIBERO.xml --indices indices.csv \
  --params-ml PO_Parametri_Mercato_Libero_E.csv \
  --params-e PO_Parametri_E.csv --operators operators.zip --out build/catalog

# Serve the API on it (see "The API" below)
BESTBILL_CATALOG_PATH=build/catalog/catalog.sqlite \
  uv run uvicorn bestbill.api.main:app --port 8000
```

`catalog build` accepts an optional `--operators <zip|xlsx|csv>` (the ARERA
"Ricerca operatori" export) to name mercato libero offers by retailer
instead of their VAT.

## Development

```bash
make install   # uv sync --locked --extra dev
make test      # pytest (marked "slow" tests need the full ARERA files, skipped by default)
make lint      # ruff, ruff format --check, mypy, shellcheck
make check     # test + lint
make smoke     # end-to-end catalogue build + API run on the synthetic sample + fixture catalogue
make openapi   # regenerate openapi.json
make catalog   # fetch + build + validate today's ARERA catalogue (network)
make catalog-publish  # build and publish the catalogue (see below)
```

CI (`.github/workflows/ci.yml`) runs install/test/lint/smoke on every push and
pull request, mirroring the `epochlater` project's setup.
The catalogue is not built in CI; see "Updating the catalogue" below.

## The backtest assumption

Every estimate answers one question: *if today's offers had applied over
your last 12 months, what would you have paid?* It assumes:

1. **Consumption repeats** — the next 12 months equal your last 12, month by
   month (and band by band, if you know your F1/F2/F3 split; otherwise a
   documented standard household split is applied and shown as an
   assumption).
2. **PUN repeats** — each month's PUN equals the PUN actually recorded in the
   *same calendar month* of your history. If a PUN month isn't published
   yet, the latest published value is used and flagged in the assumptions.

This is a **backtest, not a forecast**: it doesn't predict the future PUN, so
the fixed-vs-variable ranking can change. Every `Comparison` carries an
`assumptions` block (period, PUN months used, substituted months, band-split
source, scenario) and a human-readable Italian statement, e.g.:

> *"Spesa ipotetica nei prossimi 12 mesi, se consumassi come in set 2024 – ago 2025
> e, per le offerte a prezzo variabile, il PUN ripetesse l'andamento di quel
> periodo. È una simulazione, non una previsione."*

Variable offers also carry a **break-even PUN**: the average PUN above which
the cheapest fixed offer becomes cheaper instead.

## The ARERA catalogue

`bestbill.arera` imports the daily open data from ARERA's *Portale Offerte*
(PLACET CSV + mercato libero XML + PUN indices, CC-BY 4.0 — see
`PROVENANCE.md` and `docs/arera-data.md`) into normalised `Offer` objects,
and (optionally) the ARERA "Ricerca operatori" export (electricity-retailer
name + VAT + website, CC BY-SA 4.0) to name mercato libero offers, which
otherwise only carry a VAT number. Every pricing rule that isn't
unambiguous in the public spec — network losses, which components count as
fees vs. extras, which discounts get priced — lives in **one file**,
`bestbill.arera.policy`, so it can be corrected without touching the
parsers. Offers with an unsupported structure or an implausible reference
price are **excluded and counted**, never silently mispriced.

`bestbill.catalog.build` writes a validated, read-only `catalog.sqlite` +
`manifest.json` snapshot (schema checks, minimum offer/PUN counts, a
±30% day-to-day count gate, and a pricing-sanity check against the ARERA
reference customer). `make catalog-publish` runs this and
publishes both files (plus the operators export, cached for the next run's
fallback) to the rolling `catalog-latest` GitHub Release; a failed
validation keeps the previous snapshot serving. Because it combines CC BY
4.0 (Portale Offerte) and CC BY-SA 4.0 (ARERA operators) data, the
published catalogue as a whole is **CC BY-SA 4.0** — see `PROVENANCE.md`
for the full licence/attribution text and the manifest's `licence`/
`sources` fields.

## Aggiornare il catalogo / Updating the catalogue

ARERA's Portale Offerte blocks downloads from GitHub's servers (HTTP 403), so
no scheduled workflow can fetch it. The catalogue is built and published
**manually, from a local machine**, with one command:

```bash
make catalog-publish                  # fetch, build, validate, publish
.cicd/publish-catalog.sh --dry-run    # everything except the release upload
```

Prerequisites: `uv` and the GitHub CLI authenticated with `gh auth login`
(`jq` is used for the release notes). The repo is detected via `gh repo view`
(override with `BESTBILL_REPO=owner/name`). The script uploads only
`catalog.sqlite`, `manifest.json` and `retailers.csv` to the `catalog-latest`
release, never the raw ARERA files. The app shows the catalogue date, so
users can see how fresh the data is.

## The API

A stateless FastAPI service (`bestbill.api`) over the read-only catalogue.
Consumption and uploaded files are processed in memory per request and are
**never stored or logged** (no request-body logging; validation errors never
echo values). Every cost is the commodity/retailer cost only, before VAT
("costo materia energia (IVA esclusa)"), and a backtest — see
"The backtest assumption". Households only (residents and non-residents).

Run it locally on a catalogue built with `make catalog` (or the smoke test's
fixture catalogue in `build/smoke/catalog/`):

```bash
BESTBILL_CATALOG_PATH=build/catalog/catalog.sqlite \
  uv run uvicorn bestbill.api.main:app --reload
# interactive docs: http://127.0.0.1:8000/api/docs
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | liveness; `catalog_loaded`, snapshot date and age |
| GET | `/api/catalog/meta` | snapshot date, counts (included / excluded by reason), sources, licence, `stale` (> 3 days) |
| GET | `/api/offers` | browse offers (`price_type`, `source`, `supplier`, `q`, `limit`, `offset`) |
| GET | `/api/comuni?q=` | up to 20 comuni by name prefix (accent/case-insensitive), for autocomplete |
| GET | `/api/sample` | the synthetic sample household's 12 months |
| POST | `/api/compare` | 12 months of kWh (+ optional F1/F2/F3), `residency`, `istat_comune`, `committed_power_kw`, `scenario`, `filters`, `top_n` → ranked offers + assumptions |

`/api/compare`, `/api/offers` and `/api/catalog/meta` return 503 until a
catalogue is loaded. Every compare response carries the assumptions (Italian
statement, period, PUN months used or substituted, band-split source,
scenario, cost label) and the catalogue snapshot date. `rank` and
`delta_vs_best_eur` are computed over all eligible offers, before the
`filters` are applied. Validation errors are `422` with
`{"detail": [{"field", "message"}]}` in Italian. The OpenAPI schema is
committed as `openapi.json` (`make openapi` refreshes it; a test fails when
it is stale) and the frontend generates its types from it.

Hardening: body limits (64 KB) enforced before reading
the body, an in-memory per-IP rate limit (60 req/min, compare 20/min;
`/api/health` exempt), security headers (CSP, `X-Frame-Options: DENY`,
`nosniff`, `Referrer-Policy`), CORS off unless configured, and a generic 500
handler that logs only the exception type.

Configuration (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `BESTBILL_CATALOG_PATH` | – | Local `catalog.sqlite` (dev/tests); takes precedence over the release |
| `BESTBILL_REPO` | `leonardoburalli/bestbill` | GitHub repo holding the catalogue release |
| `BESTBILL_RELEASE_TAG` | `catalog-latest` | Release tag with `catalog.sqlite`, `manifest.json`, `retailers.csv` |
| `GITHUB_TOKEN` | – | Read-only token; only for a private repo. Leave it **unset** once public (a revoked token makes GitHub answer 401) |
| `BESTBILL_CACHE_DIR` | system temp dir | Where the downloaded catalogue is cached |
| `BESTBILL_REFRESH_HOURS` | `6` | How often to check the release for a newer catalogue |
| `BESTBILL_TRUST_PROXY` | off | `1`: rate-limit by the first `X-Forwarded-For` entry (behind Render) |
| `BESTBILL_CORS_ORIGINS` | empty | Comma-separated allowed origins (production is same-origin) |

Without `BESTBILL_CATALOG_PATH` the app downloads the release assets at
startup (it starts serving `/api/health` right away, with `catalog_loaded:
false`, until the download finishes), verifies the `sha256` from
`manifest.json`, swaps the file in atomically, and re-checks every
`BESTBILL_REFRESH_HOURS`. Without `GITHUB_TOKEN` (public repo) it only uses the
public release download URLs
(`https://github.com/<repo>/releases/download/<tag>/<asset>`), which are not
subject to the unauthenticated GitHub API quota (60 req/h per IP, easily
exhausted on shared hosts): it fetches the small `manifest.json` and downloads
`catalog.sqlite` only when its `sqlite_sha256` differs from the loaded one.
With a token (private repo) it uses the GitHub API instead. If a refresh
fails, the last good catalogue keeps serving and a warning is logged (HTTP
403/429 include the `Retry-After` / `X-RateLimit-Reset` hint when present).

## Deploy

The live setup is Vercel (front end) → Render (API, Docker) → a GitHub
Release holding the catalogue, all on free plans. Step-by-step instructions,
including what to change when you fork, are in
[`docs/deploy.md`](docs/deploy.md).

## Data & privacy

- `src/bestbill/data/sample.json` is a **synthetic** sample household
  served by `/api/sample`; it contains no real data.
- The engine has no network or storage side effects: consumption data lives
  only in memory for the duration of a run.
- The ARERA catalogue is public reference data (offers, PUN), refreshed as a
  daily snapshot; see `PROVENANCE.md` for licence, attribution and what's
  transformed. Consumption data is never stored or logged, in the CLI or
  the API.

## Repository layout

```
src/bestbill/
├── core/          # models, band splitting, the pure cost engine
├── arera/         # ARERA importer: codes, policy, placet/mlibero/indices, fetch
├── catalog/       # build/validate catalog.sqlite + manifest.json, read-only store
├── api/           # FastAPI app: routes, schemas, catalogue loader, middleware
├── geo.py         # ISTAT comuni -> provincia -> regione lookup and search
├── data/          # comuni.csv, sample.json (synthetic sample household)
└── cli.py         # command-line interface (catalog build/fetch)
scripts/make_comuni.py  # regenerates data/comuni.csv from ISTAT
scripts/export_openapi.py  # writes openapi.json (make openapi)
tests/             # pytest suite + tests/fixtures/arera (trimmed real samples, CC-BY 4.0)
```

See `PLAN.md` for the full architecture and roadmap (React frontend), `docs/arera-data.md` for the ARERA code tables and observed
findings, and `PROVENANCE.md` for data sources, licence and attribution.
