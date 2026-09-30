# Pricing policy v1 (decided 2026-09-28; source: Regole calcolo spesa annua stimata v4.0)

Scope: commodity / retailer-dependent costs only, before VAT. Never include network, system charges, excise or VAT.

## Energy
- Fixed offers (PLACET and mercato libero): Σ_band price_b × kWh_b. NO losses (published prices already include them).
- Mercato libero variable, IDX 12 or 01 (both treated as monthly PUN): Σ_months Σ_bands [PUN_m × 1.10 + spread_b] × kWh. Losses apply to the INDEX ONLY (§3.3.1.5).
- PLACET variable: Σ 1.10 × (PUN_m + α) × kWh (§3.1.1.3).
- Other IDX codes (08, 05, …) → exclude and count. TIPOLOGIA_FASCE 07 → exclude and count.
- Monthly single-rate PUN is applied to every band (the band-specific index isn't available). Documented as an assumption.

## Maggior Tutela (user decision: exclude)
Maggior Tutela is closed to new customers, so any offer referencing it is excluded with reason "riferita a Maggior Tutela":
- IDX_PREZZO_ENERGIA 05 (PE Maggior Tutela)
- TIPO_DISPACCIAMENTO 02 (PD_MT) or 10 (capacity MT)
- Sconto TIPOLOGIA 04 (discount on Maggior Tutela)
- also skip MT-only parameters (e.g. cpty_mrkt_mt).

## Other supplier components (ComponenteImpresa)
- MACROAREA 01, UM 01 (€/year) → fixed fee. UM 05 (€) → one-off, added to the 12-month total.
- MACROAREA 02, UM 03 → €/kWh on total kWh (no losses).
- MACROAREA 04, UM 03 → energy price or spread per band. UM 02 → €/kW/year × committed power (default 3 kW).
- MACROAREA 05, UM 05 → one-off, added.
- MACROAREA 06, UM 01 → €/year. UM 03 → €/kWh (no losses).
- Any other combination → exclude and count.
- ComponentiRegolate (CRPPE/CRPCV) → ignore.

## Dispatching (per offer; values from PO_Parametri_Mercato_Libero_E_{date}.csv for mercato libero, PO_Parametri_E_{date}.csv for PLACET; VERIFIED §3.1.3, §3.3.3)
Codes declared by one offer are additive (no overlap by construction). Unit €/kWh × total kWh unless noted.
| code | formula | losses ×1.10 |
|---|---|---|
| 14 | cdispd (bundles 01 + 09; never combined with them) | no |
| 01 | Cdisp = msd+modeol+uniess+terna+capprod+interr | yes |
| 03/04/05/06/07/08 | msd / modeol / uniess / terna / capprod / interr | yes |
| 09 | mean(cpty_mrkt_1, cpty_mrkt_2, cpty_mrkt_3), applied to all 12 months (flag "approximate: current quarter") | no |
| 13 | dispbt_d, €/year fixed | no |
| 99 | VALORE_DISP from the XML | no |
| 11 / 12 | rst / rstg (non-domestic only; if they appear on a domestic offer, exclude) | no |
| 02 / 10 | Maggior Tutela → exclude the offer | – |
| missing parameter or unknown code | exclude with a reason | – |
- Ignore csed and cpstgd (Servizio a Tutele Graduali only).
- PLACET domestic (fixed and variable): dispbt_d €/year + cdispd × kWh, no losses.
- Sanity invariant, logged in the manifest: Cdisp + mean(cpty_mrkt_1..3) ≈ cdispd (±1e-6); warn if not.

## Discounts
- Include only CONDIZIONE_APPLICAZIONE 00 with VALIDITA 01 or 02.
- IVA_SCONTO 01: subtract the nominal amount. IVA_SCONTO 02: subtract nominal ÷ 1.10 (flat 10% household VAT).
- TIPOLOGIA 01 (UM 01 €/year or UM 05 €): fixed amount. TIPOLOGIA 03 (UM 03 €/kWh): × kWh. UM 06 (%): applied to the energy base (fixed: Σ MACROAREA 04 energy; variable: PUN×1.10 + spread).
- Conditional discounts: kept for display only, with their description.
- **Consumption-tiered €/kWh discounts** (PrezziSconto VALIDO_DA/VALIDO_FINO,
  observed on the real "ATENA SECONDA CASA LUCE" offer and others): the
  discount only applies to the annual kWh inside `[VALIDO_DA, VALIDO_FINO)`,
  not the whole annual consumption (bug fixed 2026-09-28 -- see
  `docs/arera-data.md` "Consumption-tiered prices and discounts"). Multiple
  PrezziSconto tiers on the same Sconto are additive over their ranges.
- **Month-limited €/kWh discounts** (Sconto/PeriodoValidita/DURATA, only
  ever observed on €/kWh discounts): apply only to the kWh consumed in the
  first `DURATA` months of the 12-month estimate (capped at 12). Any other
  PeriodoValidita form (VALIDO_FINO, MESE_VALIDITA) on a discount that
  would otherwise be priced excludes the whole offer (ambiguous mapping
  onto the rolling 12-month window).
- Sconto/CODICE_COMPONENTE_FASCIA (per-band discount targeting) isn't
  implemented; a priced Sconto carrying it excludes the whole offer.

## Offer duration

Each offer exposes `duration_months` (months the economic conditions are
guaranteed) and `duration_open_ended`. Duration is informational: it never
affects the cost.

- Mercato libero: `DettaglioOfferta/DURATA`. `-1` and `99` are open-ended
  (`OPEN_ENDED_DURATA` in `arera/policy.py`; **pending confirmation against
  ARERA spec**). Missing/invalid values are unknown (`null` + `false`).
- PLACET: no column; ARERA regulation fixes PLACET conditions at 12 months.
- Filter `min_duration_months` keeps offers with `duration_months >= value`;
  open-ended and unknown offers are excluded.
- Old catalogues without these keys still load (unknown), so no schema bump.

## Consumption-tiered component prices (ComponenteImpresa CONSUMO_DA/CONSUMO_A)
- The price applies to the portion of the offer's own band annual
  consumption inside `[CONSUMO_DA, CONSUMO_A]`, additive/marginal like a
  tax bracket (confirmed by the 000190* sample offer's own description);
  *inferred*, see `docs/arera-data.md`.
- Only supported on MACROAREA 04/06 (energy price for fixed offers,
  spread for variable offers); MACROAREA 02 (per-kWh extras, not banded in
  the model) and any fixed/power/one-off fee with CONSUMO_DA/CONSUMO_A
  excludes the offer with "prezzi a scaglioni non supportati" rather than
  guess.
- Overlapping/inconsistent tier rows also exclude the offer with the same
  reason.

## Guardrail: unhandled price-affecting elements
Any child element inside IntervalloPrezzi, PrezziSconto or a *priced*
Sconto that isn't in this document's known list excludes the whole offer
with reason "elemento di prezzo non gestito: <path>/<TAG>" -- see
`docs/arera-data.md` for the full scan of the real catalogue and which
tags this currently affects (IntervalloPrezzi/PeriodoValidita, Sconto/
CODICE_COMPONENTE_FASCIA).

## RiferimentiPrezzoEnergia/COEFFICIENTE
Only COEFFICIENTE == "1" (a no-op) is accepted; any other value, or more
than one RiferimentiPrezzoEnergia on the same offer, excludes the offer
rather than guess at combining multiple indices (verified against the
real catalogue: every domestic offer transmits COEFFICIENTE "1" with a
single index).

## Result breakdown per offer
energy, fixed fees, other €/kWh, power fee, dispatching, one-off, discounts, total. Label: "costo materia energia (IVA esclusa)".

## Break-even PUN edge cases (Phase 2, decided 2026-09-28)
A variable offer's annual cost is linear in the flat average PUN `P`:
`cost_var(P) = k*P + rest`, with `k = total_kwh * index_multiplier` always
positive when there's consumption to price (the loss multiplier is 1.0 or
`1 + LOSSES`, never zero/negative). Against the cheapest eligible fixed
offer's constant cost `C`, `cost_var(P) < C` exactly for `P < break_even =
(C - rest) / k`. Three cases, `BreakEvenStatus`:
- `cheaper_below` (normal): `break_even > 0` — cheaper below that PUN, more
  expensive above it. `break_even_pun_eur_kwh` is set.
- `never_cheaper`: `break_even <= 0` — the variable offer costs at least as
  much as the best fixed offer at every non-negative PUN, so there's no
  informative number to show; `break_even_pun_eur_kwh` is `None`.
  Observed on the real catalogue: ATENA PLACET VARIABILE (`break_even =
  -0.0155`).
- `always_cheaper`: defensive branch for `k <= 0` (unreachable in practice
  given the `total_kwh > 0` gate and the always-positive loss multiplier;
  kept so the calculator never divides by zero/a negative slope).

## Supplier name resolution (Phase 2, decided 2026-09-28)
The mercato libero XML only publishes `PIVA_UTENTE` (a VAT number); PLACET
publishes `denominazione` (a name) directly. Resolution order for a
supplier's display name, `SupplierNameSource`:
1. **arera**: the ARERA "Ricerca operatori" export (RAGIONE SOCIALE),
   matched by VAT — see `bestbill.arera.operators`.
2. **placet**: a PLACET row's own `denominazione` for the same VAT (PLACET
   offers always resolve here trivially, since it's their own dataset).
3. **domain**: the retailer's own website (`URL_SITO_VENDITORE`), domain
   only (scheme/`www.`/path stripped).
4. **vat**: last resort, `"P.IVA <vat>"`.

Only `RAGIONE SOCIALE`, `PARTITA IVA` and `SITO WEB` are read from the
ARERA export; addresses and contact details are never stored (licence and
data-minimisation decision, see PROVENANCE.md). On the real catalogue: 318
of 319 mercato libero retailers resolve via **arera**; the remaining one
(VAT `03882060712`) falls back to **domain** (`rubinoenergas.it`).

## Custom offers vs. catalogue fairness (Phase 2, decided 2026-09-28)
The legacy Excel ("custom") tariffs never carried a dispatching cost,
which made them rank ~65 €/year unfairly cheaper than catalogue offers
when compared side by side. With `--catalog`, `bestbill compare` ranks
**catalogue offers only** by default; `--include-custom` adds the
workbook's offers, each priced with the catalogue's **standard household
dispatching** (`cdispd` €/kWh + `dispbt_d` €/year, from the PLACET
parameters table — the same values `bestbill.arera.policy
.placet_domestic_dispatching` uses for real PLACET offers), and flagged
with `dispatching_is_standard_estimate=True` on the result for
transparency.
