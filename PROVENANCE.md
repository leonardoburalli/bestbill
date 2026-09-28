# Provenance

BestBill's electricity-offer catalogue is derived entirely from public,
open data published by **ARERA** (Autorità di Regolazione per Energia Reti
e Ambiente) on the **Portale Offerte** (www.ilportaleofferte.it), operated
by Acquirente Unico S.p.A. under ARERA's rules (Del. 51/2018/R/com).

## Sources

| Dataset | What it is | Fetched by |
|---|---|---|
| PLACET EE (CSV) | Standard "take it or leave it" domestic/non-domestic electricity offers | `bestbill.arera.placet` |
| Mercato libero EE (XML) | Free-market electricity offers from every retailer on the portal | `bestbill.arera.mlibero` |
| Historical indices (CSV) | Monthly PUN (national single price) since 2020 | `bestbill.arera.indices` |
| Mercato libero parameters (CSV) | Dispatching parameter values (msd, modeol, cpty_mrkt_*, cdispd, ...) used to price TIPO_DISPACCIAMENTO on mercato libero offers | `bestbill.arera.parameters` |
| PLACET parameters (CSV) | Dispatching parameter values (`dispbt_d`, `cdispd`) used to price PLACET offers | `bestbill.arera.parameters` |

See `docs/arera-data.md` for exact URLs, the publication schedule, the ARERA
code tables used by the importer, and observed findings from the real data.

## Licence

**CC-BY 4.0.** The Portale Offerte "Informazioni legali" page and Del.
51/2018/R/com, Allegato A, art. 13.2(a) allow free reuse and redistribution
of the open data, including derived daily snapshots, provided the source is
cited:

> Dati elaborati a partire dagli Open Data pubblicati su "Portale Offerte"
> (www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su
> disposizioni di ARERA. Licenza CC-BY 4.0.

This attribution is embedded in every `manifest.json` and shown in the
frontend footer. Supplier and offer names are shown as part of the
comparison (nominative use), but **ARERA and Acquirente Unico logos are
never used**, and nothing on this site implies their endorsement.

## What we transform

Every day, `bestbill catalog build` (see `.github/workflows/catalog.yml`,
cron `00:00 UTC`):

1. Downloads the day's PLACET CSV, mercato libero XML, PUN indices CSV and
   the two dispatching parameters CSV files (falling back to the previous
   day's files, up to 3 days back, if a file is missing or late — ARERA
   typically publishes 22:30–23:05 UTC on D-1).
2. Parses domestic electricity offers only, normalising prices, fees,
   discounts, eligibility and geographic restrictions into a common
   `Offer` model (`bestbill.core.models`). Every pricing decision that
   isn't unambiguous in the public spec lives in **one file**,
   `bestbill.arera.policy`, so it can be corrected without touching the
   parsers.
3. Excludes and **counts** (never silently drops) offers with an
   unsupported structure (dual-fuel, unrecognised codes, incomplete
   prices) or an implausible price against the ARERA reference customer
   (2,700 kWh/year, 3 kW).
4. Writes a read-only `catalog.sqlite` + `manifest.json` (snapshot date,
   source file names, sha256, counts by source/reason, this attribution
   text, schema version), validated against schema and sanity gates before
   publishing.
5. Publishes both files to the rolling GitHub Release `catalog-latest`; if
   validation fails, the previous snapshot keeps serving.

No supplier's contractual documents (offer PDFs, GENERAL conditions) are
reproduced; only the structured fields published in the open data files are
used, exactly as required by law.

## What we don't do

- We don't store or log user consumption data — it's processed in memory
  per request and never persisted (see `PLAN.md` §10).
- We don't scrape supplier websites; every field comes from the ARERA open
  data files.
- We don't use ARERA's or Acquirente Unico's names or logos to imply
  endorsement of BestBill.
- We don't add network charges, system charges, excise duties or VAT to
  any estimate: they're regulated and identical for every supplier, so
  they never change which offer is cheapest. Every estimate is labelled as
  the commodity/supplier cost, never as the full electricity bill, and
  there is no full-bill calculation path in this codebase.
- We don't price Maggior Tutela: it's closed to new customers, so any
  offer referencing it (IDX_PREZZO_ENERGIA 05, TIPO_DISPACCIAMENTO 02/10,
  a Maggior Tutela discount) is excluded and counted, never priced.

## Snapshot cadence

- **Daily**, via the `catalog` GitHub Action (`0 0 * * *` UTC, plus manual
  `workflow_dispatch`).
- The catalogue holds **the current snapshot only** — there is no history,
  because an expired offer can't be activated anyway.
- The frontend/API re-download the snapshot on start and periodically
  (ETag-checked), so a validation failure never serves a broken catalogue;
  it keeps the last good one.
