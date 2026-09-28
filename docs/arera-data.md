# ARERA Portale Offerte — data notes

Reference for the Phase 2 importer. Entries marked *inferred* were derived from the
data, not from an official spec, and must be verified against the spec before use.

## Sources
- ARERA Del. 51/2018/R/com, [Allegato A (valid from 1 Apr 2026)](https://www.arera.it/fileadmin/allegati/docs/18/51-18_Allegato_A__valido_dall_1_aprile_2026.pdf) — portal rules, licence (art. 13.2(a)).
- Acquirente Unico / SII, [*Regole per il calcolo della spesa annua stimata* v4.0 (16 Feb 2026)](https://www.ilportaleofferte.it/portaleOfferte/resources/cms/documents/7d0a872b48e8796c84366afedd2ce7ec.pdf) — calculation method and most code tables.
- SII, *Funzionamento e Specifiche del Processo di Trasmissione Offerte* (rev. 15 Dec 2025), on the [SII public portal](https://siiportale.acquirenteunico.it/processi/trasversali/mercato-retail).
- [Portal "Informazioni legali"](https://www.ilportaleofferte.it/portaleOfferte/it/informazioni-legali.page).
- ARERA [Ricerca operatori](https://www.arera.it/area-operatori/ricerca-operatori) — electricity-retailer list (name, VAT, website), used to name mercato libero offers (see "Supplier names" below).

## Licence
CC-BY 4.0 for the Portale Offerte data (offers, parameters, indices). Reuse and redistribution of daily derived snapshots are allowed, with attribution:

> Dati elaborati a partire dagli Open Data pubblicati su "Portale Offerte"
> (www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su disposizioni di
> ARERA. Licenza CC-BY 4.0.

The ARERA "Ricerca operatori" export (arera.it site data, distinct from the
Portale Offerte data above) is licensed **CC BY-SA 4.0** per the arera.it
site terms ("Riuso dei dati pubblici (Open Data) e copyright", updated 27
Mar 2025). Since the published catalogue combines both, the catalogue
(`catalog.sqlite` + `manifest.json`) as a whole is licensed **CC BY-SA
4.0** — see PROVENANCE.md for the full attribution text and `manifest.json`'s
`licence`/`sources` fields.

Supplier and offer names may be shown (nominative use in a comparison). ARERA/AU
logos may not be used without written authorisation.

## Supplier names (ARERA "Ricerca operatori" export)
The mercato libero XML only publishes `PIVA_UTENTE` (a VAT number); the
ARERA operators export resolves it to a display name. The
"Ricerca operatori" page links to the current export as
`/fileadmin/ricercaoperatori/export-mercato-vend<DD_MM_YYYY_HH_MM_SS>.zip`
(the timestamp changes at every ARERA refresh — `bestbill.arera.operators
.discover_export_url` finds it with a regex). The zip holds one `.xlsx`
(`Sheet1`, header `RAGIONE SOCIALE | PARTITA IVA | ID_SOGGETTO | COMUNE
SEDE LEGALE | INDIRIZZO | SITO WEB | CONTATTI CLIENTE | CONTATTI CLIENTE
2`, 734 rows as of 2026-09-21). This importer reads **only** `RAGIONE
SOCIALE`, `PARTITA IVA` and `SITO WEB` — addresses and contact details are
never stored or published (data-minimisation decision, see
PROVENANCE.md). The catalogue pipeline never republishes the raw
zip/xlsx either: `bestbill.catalog.build` writes the parsed rows to a
minimised `retailers.csv` (`partita_iva,ragione_sociale,sito_web`, UTF-8,
next to `catalog.sqlite`), which is what `.cicd/catalog.sh`/
`.github/workflows/catalog.yml` publish and cache for the next day's
fallback (`bestbill.arera.operators.write_operators_csv`/
`parse_operators_csv`). `PARTITA IVA` is zero-padded to 11 digits (openpyxl can
hand back a bare number for a numeric-looking VAT); names may have
trailing spaces (e.g. `"+Energia "`), stripped at parse time. See
`docs/pricing-policy.md` "Supplier name resolution" for the full name
resolution order and the observed 318/319 real-catalogue match rate.

## Files and schedule
Base: `https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv/`
(month folder has no leading zero, file date is zero-padded):

| Dataset | Path |
|---|---|
| Mercato libero EE (XML) | `offerteML/{YYYY}_{M}/PO_Offerte_E_MLIBERO_{YYYYMMDD}.xml` |
| Mercato libero parameters | `parametriML/{YYYY}_{M}/PO_Parametri_Mercato_Libero_E_{YYYYMMDD}.csv` |
| PLACET EE (CSV) | `offerte/{YYYY}_{M}/PO_Offerte_E_PLACET_{YYYYMMDD}.csv` |
| PLACET parameters | `parametri/{YYYY}_{M}/PO_Parametri_E_{YYYYMMDD}.csv` |
| Historical indices (PUN monthly since 2020, `;`-separated, decimal comma) | `/portaleOfferte/resources/cms/documents/5d6f1085b4d5f20821af55764e647671.csv` |

Files are published 22:30–23:05 UTC on day D-1, and older daily files stay
downloadable. Cron: **00:00 UTC**. If a file is missing, retry with backoff, then
fall back to D-1 and tag the effective date in the manifest.

## Band split (household, when bill bands are unknown)
F1 33 %, F2 31 %, F3 36 % (F23 = 67 %). ARERA reference customer ("cliente tipo"): 2,700 kWh/year at 3 kW.

## XML code tables (namespace `http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01`)
| Element | Codes |
|---|---|
| TIPO_MERCATO | 01 mercato libero |
| TIPO_CLIENTE | 01 domestic, 02 non-domestic |
| DOMESTICO_RESIDENTE | 01 residents only, 02 non-residents only, 03 both |
| TIPO_OFFERTA | 01 fixed (≥12 months), 02 variable/indexed (incl. mixed) |
| TIPOLOGIA_ATT_CONTR | 01 switch, 02 subentro, 03 new activation, 04 voltura, 99 any (*inferred*) |
| TIPOLOGIA_FASCE | 01 mono (F0), 03 F1/F2/F3, 91 F1/F23, 07 custom peak/off-peak (*inferred*) |
| FASCIA_COMPONENTE | 01 F1 (or F0 for mono), 02 F2, 03 F3, 91 F23, 07/08 custom (*inferred*) |
| IDX_PREZZO_ENERGIA | 12 PUN Index GME monthly (~96 % of offers); 01, 08 (*inferred*), 05 PE Maggior Tutela |
| TIPO_DISPACCIAMENTO | 01 C_disp, 02 PD_MT, 03 MSD, 09 capacity market, 10 capacity MT, 11 RST, 12 RSTG, 13 DispBT fixed €/year, 14 C_dispD (from 1 Apr 2026), 99 other (`VALORE_DISP`) |
| ComponenteImpresa/MACROAREA | 01 fixed commercial fee, 02 variable commercial/energy, 04 energy sales quota (spread on index), 05 one-off fee, 06 renewable energy price |
| ComponenteImpresa/TIPOLOGIA | 01 standard, 02 indexed/tiered (*inferred*) |
| UNITA_MISURA | 01 €/year, 02 €/kW/year, 03 €/kWh, 04 €/Smc, 05 € one-off, 06 % |
| MODALITA_PAGAMENTO | 01 SDD, 02 postal slip, 03 card, 04 bank transfer, 99 other (*inferred*) |
| Sconto/VALIDITA | 01 on entry, 02 within 12 months, 03 beyond 12 months (excluded from annual estimate) |
| Sconto/CONDIZIONE_APPLICAZIONE | 00 unconditional (included in estimate); 01/02/03/99 conditional (show only; meanings *inferred*) |
| Sconto/PrezziSconto/TIPOLOGIA | 01 fixed (€/year or €), 03 sales (€/kWh or %), 04 on Maggior Tutela |
| Sconto/IVA_SCONTO | 01 before VAT, 02 after VAT |
| ZoneOfferta | absent = national; otherwise REGIONE (2-digit ISTAT), PROVINCIA (3-digit), COMUNE (6-digit) |

## PLACET CSV
- `p_fix_f` / `p_fix_v`: annual fee in €/year, for fixed and variable offers respectively.
- `p_vol_mono` / `p_vol_bf1` / `p_vol_bf23`: household prices in €/kWh (mono or F1/F23).
- `p_vol_f1..f3`: non-domestic trioraria prices in €/kWh.
- `alpha`: spread over PINGM (monthly PUN Index GME) in €/kWh.
- Geography: ~9 % of rows restrict by semicolon-separated ISTAT codes; blank means national.

## Methodology points that affect our engine
- **Network losses**: **verified** against AU "Regole per il calcolo della
  spesa annua stimata" v4.0. Fixed offers (both ARERA sources) get **no**
  losses. Mercato libero variable offers apply `(1 + λ)` with λ = 10 % to
  the **index only**, not the spread. PLACET variable offers apply
  `(1 + λ)` to **(PINGM + alpha) together**. See
  `bestbill.core.models.LossesMode` and `bestbill.arera.policy.losses_mode()`.
- **IDX_PREZZO_ENERGIA 01 and 12** are both treated as the monthly PUN
  index (`bestbill.arera.policy.SUPPORTED_IDX_CODES`); 01 is *inferred* to
  behave like 12 (not distinguished in the sample data).
- **Unconditional discounts** in the first 12 months reduce the estimate. Conditional discounts are only displayed.
- **Dispatching components** (C_disp/C_dispD, capacity market, …) are supplier-side €/kWh or €/year charges and belong in the supplier component; see the dispatching table below.
- **Resident/non-resident**: needed for offer eligibility (and later for excise and system charges).

## Dispatching (TIPO_DISPACCIAMENTO), verified against v4.0 §3.1.3/§3.3.3
Priced from `PO_Parametri_Mercato_Libero_E_{date}.csv` (mercato libero) /
`PO_Parametri_E_{date}.csv` (PLACET), parsed by `bestbill.arera.parameters`.
Codes declared by one offer are additive by construction (no overlap).
Unit is €/kWh × total kWh unless noted; see `bestbill.arera.policy` for the
exact implementation and `docs/pricing-policy.md` for the approved rules.

| code | formula | losses ×1.10 |
|---|---|---|
| 14 | `cdispd` (bundles 01 + 09; never combined with them) | no |
| 01 | Cdisp = msd+modeol+uniess+terna+capprod+interr | yes |
| 03/04/05/06/07/08 | msd / modeol / uniess / terna / capprod / interr | yes |
| 09 | mean(cpty_mrkt_1, cpty_mrkt_2, cpty_mrkt_3), applied to all 12 months (flagged "approximate") | no |
| 13 | `dispbt_d`, €/year fixed | no |
| 99 | `VALORE_DISP` from the XML | no |
| 11 / 12 | rst / rstg (non-domestic only; excluded if found on a domestic offer) | no |
| 02 / 10 | Maggior Tutela → excludes the whole offer | – |
| missing parameter or unknown code | excludes the offer with a reason | – |

`csed` and `cpstgd` are ignored (Servizio a Tutele Graduali only).
PLACET domestic offers (fixed and variable) always price
`dispbt_d` €/year + `cdispd` €/kWh, no losses.

**Sanity invariant**, logged in the manifest (`dispatching_identity`) and
warned on if it doesn't hold within ±1e-6:
`Cdisp + mean(cpty_mrkt_1..3) ≈ cdispd`.

## Maggior Tutela exclusion (user decision, docs/pricing-policy.md)
Maggior Tutela is closed to new customers, so any offer referencing it is
excluded with reason "riferita a Maggior Tutela":
- `IDX_PREZZO_ENERGIA` 05 (PE Maggior Tutela).
- `TIPO_DISPACCIAMENTO` 02 (PD_MT) or 10 (capacity MT).
- `Sconto/PrezziSconto/TIPOLOGIA` 04 (discount on Maggior Tutela).
- MT-only parameters (e.g. `cpty_mrkt_mt`) are never used in pricing.

## Observed findings (Phase 2 importer, from the real files)
- **MACROAREA 06 behaves exactly like MACROAREA 04** (energy price for fixed
  offers / spread for variable offers, per `FASCIA_COMPONENTE` band), not a
  separate per-kWh extra. Confirmed on real fixed offers where MACROAREA 06
  is the *only* `ComponenteImpresa` (e.g. "Prezzo Componente Energia
  Elettricità", 100% renewable offers) and the parsed offer has no other
  energy-price component. `bestbill.arera.policy.classify_component` routes
  06 the same way as 04.
- **UNITA_MISURA 02 (€/kW/year)** is used both under MACROAREA 04 (e.g.
  "Corrispettivo Quota Potenza da BTA1 a BTA3") independent of MACROAREA —
  the importer classifies any component with `UNITA_MISURA == "02"` as the
  power fee regardless of its MACROAREA.
- **TIPO_DISPACCIAMENTO 13 (DispBT fisso €/anno)**: when a `VALORE_DISP` is
  present it is a €/year fixed fee, not a €/kWh extra; other dispatching
  codes with a `VALORE_DISP` (99 and, occasionally, others) are treated as
  €/kWh extras. Regulated codes (01, 02, 03, 09-12, 14) normally carry no
  `VALORE_DISP` in the sample file and are ignored, per the "same across
  suppliers" rationale above.
- **Mercato libero XML has no supplier company name element**, only
  `PIVA_UTENTE` (VAT number). The catalogue currently shows `"P.IVA
  <number>"` as the supplier name for mercato libero offers; a real
  deployment should join against ARERA's operator list (or the
  `parametriML` file, not fetched in this phase) for a display name. PLACET
  rows do carry `denominazione` (supplier name) directly.
- **PLACET domestic variable offers with no `p_vol_*` columns** are priced
  purely as PINGM (PUN monthly index) + `alpha`; the importer defaults them
  to a `mono` band structure with a zero base price and `alpha` as spread.
- **MACROAREA 02 can also hold the actual energy price** (observed: a fixed
  offer named its MACROAREA 02 component "Sales Price" / "Prezzo Energia",
  banded by `FASCIA_COMPONENTE`, with no MACROAREA 04/06 component at all).
  **Fixed 2026-09-28**: for a `mono` (monorario) fixed offer with no
  MACROAREA 04/06 component at all, `energy_price_eur_kwh["mono"]`
  defaults to `0.0` and the whole price is priced via
  `per_kwh_extras_eur` instead (already routed there by
  `classify_component`, MACROAREA 02 → `PER_KWH_EXTRAS`) -- same annual
  cost, no losses either way (fixed offers never get losses). Confirmed
  on 17 real domestic offers (all `mono`, e.g. "E.CO Luce Prezzo Sicuro
  Link" `000742ESFML01XXSICREFIX260930D01`), previously excluded as
  "prezzi energia incompleti". Deliberately **not** extended to banded
  (F1/F2/F3 or F1/F23) MACROAREA-02-only offers: `per_kwh_extras_eur` is
  a flat, unweighted average of every MACROAREA 02 row
  (`bestbill.arera.mlibero._parse_componenti`), which would misprice a
  banded offer whose bands don't share the same consumption weight as a
  simple average assumes; no such offer was observed in the real
  catalogue, so those still exclude with "prezzi energia incompleti"
  rather than guess.

## Consumption-tiered prices and discounts (bug fixed 2026-09-28)
The catalogue used to price a discount or a component's whole annual kWh
against its nominal €/kWh amount even when the XML restricted it to a
consumption band -- e.g. "ATENA SECONDA CASA LUCE"
(`000567ESFML12XX0000AEDOSCL261011`) subtracted `0.07568 × 2700` (all of
the sample's 2,700 kWh) instead of `0.07568 × 840` (the first 840 kWh/year
only), ranking it #1 at 438.44 € instead of its correct ≈579.21 €. Full
scan of the real mercato libero XML (2026-09 snapshot, `e_ml.xml`):

| element | rows (domestic) | unique domestic offers | handling |
|---|---|---|---|
| `Sconto/PrezziSconto/VALIDO_DA`+`VALIDO_FINO` | 33 | 21 (16 with a `EUR_KWH` unit; the rest are `EUR_ANNO`/`EUR_UNA_TANTUM` with the `999999`/`999999999` "no limit" sentinel, irrelevant to those units) | implemented: marginal tiers on annual consumption, additive across `PrezziSconto` rows on the same `Sconto` |
| `Sconto/PeriodoValidita` (any form) | 84 rows / 40 unique | 19 unconditional+priced, **all `DURATA` only** (12/30/1/3 months, always on a `EUR_KWH` discount) | implemented: prorate to the kWh in the first `DURATA` months (capped at 12) |
| `Sconto/CODICE_COMPONENTE_FASCIA` | 71 rows | 12 unconditional+priced | **not implemented** -- excludes via the guardrail (per-band discount targeting; the current `Discount`/`discount_annual_value_eur` model has no per-band base) |
| `ComponenteImpresa/IntervalloPrezzi/CONSUMO_DA`+`CONSUMO_A` | 20 | 6 | implemented for MACROAREA 04/06 (energy price/spread) only: marginal tiers on the band's own annual kWh, additive with any flat (non-tiered) price on the same band. MACROAREA 02 (per-kWh extras) and any fixed/power/one-off-fee component with `CONSUMO_DA` excludes the offer ("prezzi a scaglioni non supportati") -- ambiguous (extras aren't banded in the model) |
| `ComponenteImpresa/IntervalloPrezzi/PeriodoValidita` | 33 rows / 19 unique | 12 domestic | **not implemented** -- excludes via the guardrail (a temporally-restricted component price, always mixed with a same-value "default" row in the sample data; summing both would double-count, and picking one over the other for a rolling 12-month estimate is ambiguous without the full SII transmission spec) |
| `RiferimentiPrezzoEnergia/COEFFICIENTE` | 38 rows, all domestic | 38 | every value observed is `"1"` (no-op) and no domestic offer transmits more than one `RiferimentiPrezzoEnergia`; only that no-op case is accepted, anything else excludes the offer |
| `ComponenteImpresa/IntervalloPrezzi/DETTAGLI_MACROAREA` | 0 (only ever seen under `ProdottiServiziAggiuntivi/MACROAREA`, which isn't priced at all) | 0 | not reachable by the parser; no change needed |

**Guardrail** (`bestbill.arera.mlibero`): any child element inside
`IntervalloPrezzi`, `PrezziSconto`, or a *priced* `Sconto` that isn't on
the known list above excludes the whole offer with reason "elemento di
prezzo non gestito: `<path>/<TAG>`", so nothing else in a future snapshot
is silently mispriced. Running the scan above over the full real
2026-09 snapshot found exactly the two tags in the table
(`IntervalloPrezzi/PeriodoValidita`, `Sconto/CODICE_COMPONENTE_FASCIA`);
no other unknown tag triggered it.

The marginal (tax-bracket-style) tiering for both discounts and component
prices is *inferred*: the copy of AU "Regole per il calcolo della spesa
annua stimata" v4.0 available to this importer names "offerte con
scaglioni di consumo" (§ history, changelog 3.00) without a full worked
formula for `CONSUMO_DA`/`CONSUMO_A`, and doesn't cover `Sconto`'s
`VALIDO_DA`/`VALIDO_FINO` fields at all (only `IntervalloPrezzi/
PeriodoValidita/VALIDO_FINO`, which is a **calendar month**, a different
field in a different context). The marginal interpretation is confirmed
by two real offers' own free-text descriptions ("Fino alla soglia di 2200
kWh/anno sarà applicato ... Oltre tale soglia ...", "sconto del 40% sui
primi 840 kWh/a").
