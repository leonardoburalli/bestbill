# Provenance

BestBill's electricity-offer catalogue is derived from two public, open
data sources: **ARERA** (Autorità di Regolazione per Energia Reti e
Ambiente) publishes the offers, dispatching parameters and PUN indices on
the **Portale Offerte** (www.ilportaleofferte.it), operated by Acquirente
Unico S.p.A. under ARERA's rules (Del. 51/2018/R/com); ARERA also
publishes the electricity-retailer list on its own site
(www.arera.it, "Ricerca operatori"), used to name mercato libero offers
(the Portale Offerte XML only carries a VAT number, not a name — see
`docs/pricing-policy.md` "Supplier name resolution").

## Sources

| Dataset | What it is | Fetched by | Licence |
|---|---|---|---|
| PLACET EE (CSV) | Standard "take it or leave it" domestic/non-domestic electricity offers | `bestbill.arera.placet` | CC BY 4.0 |
| Mercato libero EE (XML) | Free-market electricity offers from every retailer on the portal | `bestbill.arera.mlibero` | CC BY 4.0 |
| Historical indices (CSV) | Monthly PUN (national single price) since 2020 | `bestbill.arera.indices` | CC BY 4.0 |
| Mercato libero parameters (CSV) | Dispatching parameter values (msd, modeol, cpty_mrkt_*, cdispd, ...) used to price TIPO_DISPACCIAMENTO on mercato libero offers | `bestbill.arera.parameters` | CC BY 4.0 |
| PLACET parameters (CSV) | Dispatching parameter values (`dispbt_d`, `cdispd`) used to price PLACET offers | `bestbill.arera.parameters` | CC BY 4.0 |
| ARERA "Ricerca operatori" export (XLSX in a ZIP) | Electricity-retailer name + VAT + website, used to name mercato libero offers | `bestbill.arera.operators` | CC BY-SA 4.0 |

| ISTAT "Elenco comuni italiani" (CSV) | Comune → provincia → regione codes and names, used to match a user's comune against area-restricted offers (`src/bestbill/data/comuni.csv`, built by `scripts/make_comuni.py`) | manually, `scripts/make_comuni.py` | CC BY 4.0 (ISTAT legal notes, istat.it/note-legali) |

The comuni table comes from ISTAT, "Elenco dei comuni italiani"
(https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv),
published under Creative Commons Attribution 4.0. Attribution: *Fonte:
elaborazione su dati ISTAT.* Only code, name, provincia sigla/code and
regione code/name are kept. The provincia code is ISTAT's "Codice Provincia
(Storico)", which equals the first three digits of the comune code and is
the value ARERA's `PROVINCIA` zone uses; ARERA's `REGIONE` uses the ISTAT
two-digit region code.

See `docs/arera-data.md` for exact URLs, the publication schedule, the ARERA
code tables used by the importer, and observed findings from the real data.

## Licence

The published catalogue (`catalog.sqlite` + `manifest.json`) combines data
under two licences and is therefore distributed, as a whole, under the
more restrictive one: **CC BY-SA 4.0**. The Portale Offerte "Informazioni
legali" page and Del. 51/2018/R/com, Allegato A, art. 13.2(a) license the
offers/PUN/parameters data as CC BY 4.0; the arera.it site terms
("Riuso dei dati pubblici (Open Data) e copyright", updated 27 Mar 2025)
license the "Ricerca operatori" export as CC BY-SA 4.0. Both allow free
reuse and redistribution, including derived daily snapshots, provided the
source is cited and (for the CC BY-SA 4.0 share) derivatives are licensed
under the same terms:

> Elenco venditori: ARERA – Ricerca operatori (www.arera.it), licenza CC
> BY-SA 4.0. Offerte e parametri: Portale Offerte
> (www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su
> disposizioni di ARERA, licenza CC BY 4.0. Catalogo BestBill derivato: CC
> BY-SA 4.0.

This attribution is embedded in every `manifest.json` (`licence`,
`sources`, `attribution` fields) and shown in the frontend footer.
Supplier and offer names are shown as part of the comparison (nominative
use), but **ARERA and Acquirente Unico logos are never used**, and nothing
on this site implies their endorsement. The code itself (everything in
`src/`, `tests/`, `.cicd/`, `.github/`) stays **MIT**-licensed (see
`LICENSE`); only the *data* the catalogue pipeline produces is CC BY-SA
4.0.

## What we transform

Each time the catalogue is published, `bestbill catalog build` runs
(manually from a local machine via `make catalog-publish`, because ARERA's
Portale Offerte returns HTTP 403 to GitHub Actions/cloud IPs):

1. Downloads the day's PLACET CSV, mercato libero XML, PUN indices CSV, the
   two dispatching parameters CSV files (falling back to the previous
   day's files, up to 3 days back, if a file is missing or late — ARERA
   typically publishes 22:30–23:05 UTC on D-1), and the ARERA "Ricerca
   operatori" export (falling back to the previous published snapshot's
   cached export, then to no operator names at all, if today's fetch
   fails — see `.cicd/catalog.sh`).
2. Parses domestic electricity offers only, normalising prices, fees,
   discounts, eligibility and geographic restrictions into a common
   `Offer` model (`bestbill.core.models`). Every pricing decision that
   isn't unambiguous in the public spec lives in **one file**,
   `bestbill.arera.policy`, so it can be corrected without touching the
   parsers.
3. Resolves each offer's supplier display name (ARERA operators export ->
   PLACET `denominazione` -> website domain -> `"P.IVA <vat>"`, see
   `docs/pricing-policy.md`), reading **only** the retailer's name, VAT
   and website from the ARERA export — never the addresses or contact
   details it also carries (data-minimisation decision).
4. Excludes and **counts** (never silently drops) offers with an
   unsupported structure (dual-fuel, unrecognised codes, incomplete
   prices) or an implausible price against the ARERA reference customer
   (2,700 kWh/year, 3 kW).
5. Writes a read-only `catalog.sqlite` + `manifest.json` (snapshot date,
   source file names, sha256, counts by source/reason/supplier-name-source,
   this attribution text, licence, sources, schema version), validated
   against schema and sanity gates before publishing.
6. Publishes the sqlite, manifest and a minimised `retailers.csv`
   (`partita_iva`/`ragione_sociale`/`sito_web` only — never the raw
   zip/xlsx, which also carries addresses and customer contacts; for the
   next day's fallback) to the rolling GitHub Release `catalog-latest`; if
   validation fails, the previous snapshot keeps serving.

No supplier's contractual documents (offer PDFs, GENERAL conditions) are
reproduced; only the structured fields published in the open data files are
used, exactly as required by law.

## What we don't do

- We don't store or log user consumption data — it's processed in memory
  per request and never persisted (see `PLAN.md` §10).
- We don't scrape supplier websites; every field comes from the ARERA open
  data files, except the supplier's own website *domain* (stripped of
  scheme/path), which is only ever used as a last-resort display name when
  neither the ARERA operators export nor PLACET has a name for that VAT.
- We don't store or publish the ARERA operators export's addresses or
  contact details — only name, VAT and website (data-minimisation
  decision, `bestbill.arera.operators`).
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
