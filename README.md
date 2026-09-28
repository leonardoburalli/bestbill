# BestBill

Which electricity offer is cheapest for **your own** consumption? BestBill is a
free, open-source tool for Italian households: enter 12 months of kWh, get a
ranked list of offers with a clear breakdown of the assumptions behind the
estimate — no sign-up, no personal data stored.

> Status: core engine + CLI (Phase 0–1 of `PLAN.md`). The web app (ARERA
> catalogue importer, API, React frontend) is coming next; see `PLAN.md` for
> the full roadmap.

## What it does today

- A pure, typed calculation engine (`bestbill.core`): given a 12-month
  consumption profile, a set of offers and a PUN (national single price)
  series, it ranks offers by estimated annual cost, with per-offer
  break-even PUN for variable offers.
- A legacy Excel reader (`bestbill.io.excel`) for the original
  `Tariffario` / `Storico_<Location>` workbook format.
- A CLI (`bestbill`) that reads that workbook, runs the comparison, prints a
  ranking, and writes a CSV (and optionally a bar chart).

## Quick start

```bash
# Install the locked environment (uv: https://docs.astral.sh/uv/)
make install

# Try it on the bundled synthetic sample household
uv run bestbill --file src/bestbill/data/sample.xlsx --location Esempio

# Or on your own workbook (kept out of git; see Input/ below)
uv run bestbill --file Input/TariffeEE_Bolletta.xlsx --location Milano --chart
```

`--pun {actual,forecast}` chooses which PUN series to use for variable
offers; `--output-dir` controls where the CSV (and chart) are written
(defaults to `Output/`).

## Development

```bash
make install   # uv sync --locked --extra dev
make test      # pytest
make lint      # ruff, ruff format --check, mypy, shellcheck
make check     # test + lint
make smoke     # end-to-end CLI run on the synthetic sample
```

CI (`.github/workflows/ci.yml`) runs the same four steps on every push and
pull request, mirroring the `epochlater` project's setup.

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

## Data & privacy

- `Input/` and `Output/` are local, gitignored folders for your own workbook
  and generated reports — nothing in them is ever committed.
- `src/bestbill/data/sample.xlsx` is a **synthetic** sample household
  (reproducible via `scripts/make_sample.py`); it contains no real data.
- The engine has no network or storage side effects: consumption data lives
  only in memory for the duration of a run.
- Later phases (see `PLAN.md`) add a daily ARERA offers catalogue and a
  stateless API; consumption will still never be stored or logged there.

## Repository layout

```
src/bestbill/
├── core/          # models, band splitting, the pure cost engine
├── io/excel.py     # legacy Tariffario/Storico Excel reader
├── data/sample.xlsx  # synthetic sample household
└── cli.py         # command-line interface
scripts/make_sample.py  # regenerates data/sample.xlsx
tests/             # pytest suite (≥90% coverage on core/)
```

See `PLAN.md` for the full architecture and roadmap (ARERA importer,
FastAPI backend, React frontend).
