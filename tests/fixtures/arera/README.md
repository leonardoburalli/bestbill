# ARERA fixtures

Trimmed samples from the ARERA *Portale Offerte* open data (`e_placet.csv`,
`e_ml.xml`, indices CSV), downloaded 2026-09-28, used by the parser and
catalogue tests in `tests/test_arera_*.py` and `tests/test_catalog_*.py`.

- `placet.csv`: 20 rows from `PO_Offerte_E_PLACET_*.csv` (mono and F1/F23,
  fixed and variable, domestic and non-domestic, one geo-restricted row).
- `mlibero.xml`: 13 `<offerta>` elements from `PO_Offerte_E_MLIBERO_*.xml`,
  covering mono/F1F2F3/F1F23, fixed/variable, with/without `Sconto`
  (conditional and unconditional), with/without `ZoneOfferta` (regione,
  provincia, comune), domestic and non-domestic, dual-fuel
  (`OFFERTA_SINGOLA=NO`), and unsupported `IDX_PREZZO_ENERGIA` /
  `TIPOLOGIA_FASCE` codes.
- `indices.csv`: the full historical PUN monthly series (small, kept whole).

## Licence

Dati elaborati a partire dagli Open Data pubblicati su "Portale Offerte"
(www.ilportaleofferte.it), gestito da Acquirente Unico S.p.A. su
disposizioni di ARERA. Licenza CC-BY 4.0.

See `docs/arera-data.md` and `PROVENANCE.md` for the full source, licence
and attribution details.
