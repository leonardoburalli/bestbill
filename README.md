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
- A legacy Excel reader (`bestbill.io.excel`) for the original
  `Tariffario` / `Storico_<Location>` workbook format.
- A stateless HTTP API (`bestbill.api`, FastAPI): compare, offers browse,
  comune autocomplete, Excel parse, sample household, catalogue meta.
- Area-restricted offers are matched by comune, provincia and regione using
  the ISTAT comuni table (`bestbill.geo`).
- A CLI (`bestbill`) with `compare` (ranks custom and/or catalogue offers,
  prints, writes a CSV, optionally a chart) and `catalog build|fetch`
  subcommands.

## Quick start

```bash
# Install the locked environment (uv: https://docs.astral.sh/uv/)
make install

# Try it on the bundled synthetic sample household
uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio

# Or on your own workbook (kept out of git; see Input/ below)
uv run bestbill compare --file Input/TariffeEE_Bolletta.xlsx --location Milano --chart

# Build a catalogue from ARERA source files, then rank real offers too
uv run bestbill catalog build --placet PO_Offerte_E_PLACET.csv \
  --mlibero PO_Offerte_E_MLIBERO.xml --indices indices.csv \
  --params-ml PO_Parametri_Mercato_Libero_E.csv \
  --params-e PO_Parametri_E.csv --operators operators.zip --out build/catalog
uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
  --catalog build/catalog/catalog.sqlite

# Add the workbook's own offers too, priced with the standard household
# dispatching so they're comparable to catalogue offers
uv run bestbill compare --file src/bestbill/data/sample.xlsx --location Esempio \
  --catalog build/catalog/catalog.sqlite --include-custom
```

For backwards compatibility, `bestbill --file ... --location ...` (no
subcommand) is equivalent to `bestbill compare --file ... --location ...`.

`--pun {actual,forecast}` chooses which PUN series to use for variable
offers; `--output-dir` controls where the CSV (and chart) are written
(defaults to `Output/`). `compare` also accepts `--residency
{resident,non_resident}`, `--istat-comune` (6-digit ISTAT comune code, for
geo-restricted catalogue offers) and `--committed-power-kw` (default 3.0).
With `--catalog`, only catalogue offers are ranked by default (the
workbook's custom tariffs previously had no dispatching cost, making them
unfairly cheaper); pass `--include-custom` to add them back in, priced
with the catalogue's standard household dispatching. `catalog build`
accepts an optional `--operators <zip|xlsx>` (the ARERA "Ricerca
operatori" export) to name mercato libero offers by retailer instead of
their VAT.

## Development

```bash
make install   # uv sync --locked --extra dev
make test      # pytest (marked "slow" tests need the full ARERA files, skipped by default)
make lint      # ruff, ruff format --check, mypy, shellcheck
make check     # test + lint
make smoke     # end-to-end CLI + API run on the synthetic sample + fixture catalogue
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
| POST | `/api/parse` | multipart `.xlsx` in the legacy format → consumption profiles (max 2 MB) |
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

Hardening: body limits (compare 64 KB, upload 2 MB) enforced before reading
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
| `GITHUB_TOKEN` | – | Read-only token; only needed while the repo is private |
| `BESTBILL_CACHE_DIR` | system temp dir | Where the downloaded catalogue is cached |
| `BESTBILL_REFRESH_HOURS` | `6` | How often to check the release for a newer catalogue |
| `BESTBILL_TRUST_PROXY` | off | `1`: rate-limit by the first `X-Forwarded-For` entry (behind Render) |
| `BESTBILL_CORS_ORIGINS` | empty | Comma-separated allowed origins (production is same-origin) |

Without `BESTBILL_CATALOG_PATH` the app downloads the release assets at
startup (it starts serving `/api/health` right away, with `catalog_loaded:
false`, until the download finishes), verifies the `sha256` from
`manifest.json`, swaps the file in atomically, and re-checks the asset's
`updated_at` every `BESTBILL_REFRESH_HOURS`. If a refresh fails, the last good
catalogue keeps serving and a warning is logged.

## Deploy the API to Render

The repo ships a `Dockerfile` and a `render.yaml` Blueprint (one free web
service, `bestbill-api`, Frankfurt, health check `/api/health`, auto-deploy
from `main`).

1. **Create the token** (only while the repository is private; skip if it's
   public): GitHub → Settings → Developer settings → Personal access tokens →
   *Fine-grained tokens* → Generate new token. Resource owner: you; *Only
   select repositories* → `leonardoburalli/bestbill`; Repository permissions →
   **Contents: Read-only**; pick a sensible expiry. Copy the token.
2. On [dashboard.render.com](https://dashboard.render.com): **New → Blueprint**,
   connect GitHub and select this repository. Render reads `render.yaml`.
3. When prompted for the `sync: false` variables, set **`GITHUB_TOKEN`** to the
   token from step 1, and leave `BESTBILL_CORS_ORIGINS` empty (the frontend
   is same-origin through the Vercel rewrite).
4. Click **Apply**. Once deployed, check `https://<service>.onrender.com/api/health`
   (`catalog_loaded` turns `true` after the first download) and
   `/api/docs`.

Free-plan caveats: the service spins down after ~15 minutes without traffic,
and the next request takes about 30–60 s (cold start, plus the catalogue
download because the free plan has no persistent disk). The frontend should
ping `/api/health` and show a "waking up" state. Publishing a new catalogue
with `make catalog-publish` needs no redeploy: running instances pick it up
within `BESTBILL_REFRESH_HOURS`, and a restart fetches it immediately.

## Data & privacy

- `Input/` and `Output/` are local, gitignored folders for your own workbook
  and generated reports — nothing in them is ever committed.
- `src/bestbill/data/sample.xlsx` is a **synthetic** sample household
  (reproducible via `scripts/make_sample.py`); it contains no real data.
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
├── io/excel.py     # legacy Tariffario/Storico Excel reader
├── data/sample.xlsx  # synthetic sample household
└── cli.py         # command-line interface (compare, catalog build/fetch)
scripts/make_sample.py  # regenerates data/sample.xlsx
scripts/make_comuni.py  # regenerates data/comuni.csv from ISTAT
scripts/export_openapi.py  # writes openapi.json (make openapi)
tests/             # pytest suite + tests/fixtures/arera (trimmed real samples, CC-BY 4.0)
```

See `PLAN.md` for the full architecture and roadmap (React frontend), `docs/arera-data.md` for the ARERA code tables and observed
findings, and `PROVENANCE.md` for data sources, licence and attribution.
