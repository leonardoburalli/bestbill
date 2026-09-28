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

## Result breakdown per offer
energy, fixed fees, other €/kWh, power fee, dispatching, one-off, discounts, total. Label: "costo materia energia (IVA esclusa)".
