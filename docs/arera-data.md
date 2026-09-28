# ARERA Portale Offerte — data notes

Reference for the Phase 2 importer. Entries marked *inferred* were derived from the
data, not from an official spec, and must be verified against the spec before use.

## Sources
- ARERA Del. 51/2018/R/com, [Allegato A (valid from 1 Apr 2026)](https://www.arera.it/fileadmin/allegati/docs/18/51-18_Allegato_A__valido_dall_1_aprile_2026.pdf) — portal rules, licence (art. 13.2(a)).
- Acquirente Unico / SII, [*Regole per il calcolo della spesa annua stimata* v4.0 (16 Feb 2026)](https://www.ilportaleofferte.it/portaleOfferte/resources/cms/documents/7d0a872b48e8796c84366afedd2ce7ec.pdf) — calculation method and most code tables.
- SII, *Funzionamento e Specifiche del Processo di Trasmissione Offerte* (rev. 15 Dec 2025), on the [SII public portal](https://siiportale.acquirenteunico.it/processi/trasversali/mercato-retail).
- [Portal "Informazioni legali"](https://www.ilportaleofferte.it/portaleOfferte/it/informazioni-legali.page).

## Licence
CC-BY 4.0. Reuse and redistribution of daily derived snapshots are allowed, with attribution:

> Dati elaborati a partire dagli Open Data pubblicati su "Portale Offerte"
> (www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su disposizioni di
> ARERA. Licenza CC-BY 4.0.

Supplier and offer names may be shown (nominative use in a comparison). ARERA/AU
logos may not be used without written authorisation.

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
- **Network losses**: the portal applies `(1 + λ)` with λ = 10 % (low voltage) to index + spread for variable offers. Verify whether prices already include losses, per source and per component, before pricing.
- **Unconditional discounts** in the first 12 months reduce the estimate. Conditional discounts are only displayed.
- **Dispatching components** (C_disp/C_dispD, capacity market, …) are supplier-side €/kWh or €/year charges and belong in the supplier component.
- **Resident/non-resident**: needed for offer eligibility (and later for excise and system charges).

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
  The importer keeps the brief's provisional default (02 → per_kwh_extras),
  so offers like this are currently excluded as "prezzi energia
  incompleti" — flagged in `policy.py` for the pricing-semantics review.
