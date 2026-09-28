"""Parse the ARERA historical indices CSV into a PUN monthly series.

Format (observed): ``AnnoMese;PUN (€/kWh);PSV (€/Smc);...``, semicolon
separated, decimal comma, `\\r\\n` line endings. The file is typically
cp1252/latin-1 encoded (the header has a non-UTF-8 "€" byte); this parser
detects the encoding rather than assuming one.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from bestbill.core.models import PunSeries

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

#: The PUN column is always the second one after AnnoMese, whatever its
#: exact header spelling (encoding-dependent).
_PUN_COLUMN_INDEX = 1


class IndicesFormatError(ValueError):
    """The indices file doesn't match the expected format."""


def _decode(raw: bytes) -> str:
    for encoding in _ENCODINGS_TO_TRY:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise IndicesFormatError("could not decode indices file with any known encoding")


def _parse_anno_mese(value: str) -> date:
    value = value.strip()
    if len(value) != 6 or not value.isdigit():
        raise IndicesFormatError(f"expected AnnoMese as YYYYMM, got {value!r}")
    year, month = int(value[:4]), int(value[4:6])
    if not (1 <= month <= 12):
        raise IndicesFormatError(f"invalid month in AnnoMese {value!r}")
    return date(year, month, 1)


def _parse_decimal_comma(value: str) -> float:
    return float(value.strip().replace(",", "."))


def parse_indices_bytes(raw: bytes) -> PunSeries:
    text = _decode(raw)
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        raise IndicesFormatError("indices file is empty")
    header, *data_rows = rows

    values: dict[date, float] = {}
    for row in data_rows:
        if not row or not row[0].strip():
            continue
        if len(row) <= _PUN_COLUMN_INDEX:
            raise IndicesFormatError(f"row has too few columns: {row!r}")
        month = _parse_anno_mese(row[0])
        pun = _parse_decimal_comma(row[_PUN_COLUMN_INDEX])
        values[month] = pun
    if not values:
        raise IndicesFormatError("no data rows found in indices file")
    return PunSeries(values=values)


def parse_indices_file(path: str) -> PunSeries:
    with open(path, "rb") as f:
        raw = f.read()
    return parse_indices_bytes(raw)
