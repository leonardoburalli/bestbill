# BestBill

Which electricity offer is cheapest for **your own** consumption? BestBill is a
free, open-source tool for Italian households: enter 12 months of kWh, get a
ranked list of offers with a clear breakdown of the assumptions behind the
estimate — no sign-up, no personal data stored.

> Status: core engine + CLI + ARERA catalogue importer (Phase 0–2 of
> `PLAN.md`). The web app (FastAPI, React frontend) is coming next; see
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
make smoke     # end-to-end CLI run on the synthetic sample + fixture catalogue
make catalog   # fetch + build + validate today's ARERA catalogue (network)
```

CI (`.github/workflows/ci.yml`) runs install/test/lint/smoke on every push and
pull request, mirroring the `epochlater` project's setup.
`.github/workflows/catalog.yml` runs the daily data pipeline (cron
`00:00 UTC` + manual dispatch) and publishes `catalog.sqlite` +
`manifest.json` to the rolling `catalog-latest` GitHub Release.

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

> *"Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi e il PUN siano
> identici a quelli di set 2024 – ago 2025. Non è una previsione."*

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
reference customer). `.github/workflows/catalog.yml` runs this daily and
publishes both files (plus the operators export, cached for the next run's
fallback) to the rolling `catalog-latest` GitHub Release; a failed
validation keeps the previous snapshot serving. Because it combines CC BY
4.0 (Portale Offerte) and CC BY-SA 4.0 (ARERA operators) data, the
published catalogue as a whole is **CC BY-SA 4.0** — see `PROVENANCE.md`
for the full licence/attribution text and the manifest's `licence`/
`sources` fields.

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
  later phases' API.

## Repository layout

```
src/bestbill/
├── core/          # models, band splitting, the pure cost engine
├── arera/         # ARERA importer: codes, policy, placet/mlibero/indices, fetch
├── catalog/       # build/validate catalog.sqlite + manifest.json, read-only store
├── io/excel.py     # legacy Tariffario/Storico Excel reader
├── data/sample.xlsx  # synthetic sample household
└── cli.py         # command-line interface (compare, catalog build/fetch)
scripts/make_sample.py  # regenerates data/sample.xlsx
tests/             # pytest suite + tests/fixtures/arera (trimmed real samples, CC-BY 4.0)
```

See `PLAN.md` for the full architecture and roadmap (FastAPI backend, React
frontend), `docs/arera-data.md` for the ARERA code tables and observed
findings, and `PROVENANCE.md` for data sources, licence and attribution.
