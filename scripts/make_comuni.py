"""Build ``src/bestbill/data/comuni.csv`` from the ISTAT "Elenco comuni italiani".

Source: https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv
(semicolon-separated, latin-1). Keeps only what geo-eligibility needs:
comune code (6 digits), name, province sigla, province code (3 digits: the
"Codice Provincia (Storico)" column, which is what ARERA's ``PROVINCIA``
uses and equals the first 3 digits of the comune code), region code (2
digits) and region name.

Usage: uv run python scripts/make_comuni.py [path-or-url-of-istat.csv]
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://www.istat.it/storage/codici-unita-amministrative/"
    "Elenco-comuni-italiani.csv"
)
OUT = Path(__file__).resolve().parent.parent / "src/bestbill/data/comuni.csv"
FIELDS = [
    "codice_comune",
    "nome",
    "sigla_provincia",
    "codice_provincia",
    "codice_regione",
    "nome_regione",
]


def _col(header: list[str], prefix: str) -> int:
    for i, name in enumerate(header):
        if name.strip().startswith(prefix):
            return i
    raise SystemExit(f"column starting with {prefix!r} not found")


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()  # noqa: S310
    else:
        raw = Path(src).read_bytes()
    reader = csv.reader(io.StringIO(raw.decode("latin-1")), delimiter=";")
    header = next(reader)
    i_reg = _col(header, "Codice Regione")
    i_prov = _col(header, "Codice Provincia")
    i_com = _col(header, "Codice Comune formato alfanumerico")
    i_nome = _col(header, "Denominazione in italiano")
    i_nreg = _col(header, "Denominazione Regione")
    i_sigla = _col(header, "Sigla automobilistica")
    rows = []
    for r in reader:
        if len(r) <= max(i_reg, i_prov, i_com, i_nome, i_nreg, i_sigla):
            continue
        com = r[i_com].strip().zfill(6)
        prov = r[i_prov].strip().zfill(3)
        if len(com) != 6 or com[:3] != prov:
            raise SystemExit(f"provincia {prov} != comune prefix for {com}")
        rows.append(
            [
                com,
                r[i_nome].strip(),
                r[i_sigla].strip(),
                prov,
                r[i_reg].strip().zfill(2),
                r[i_nreg].strip(),
            ]
        )
    rows.sort()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(FIELDS)
        w.writerows(rows)
    print(f"wrote {len(rows)} comuni to {OUT}")


if __name__ == "__main__":
    main()
