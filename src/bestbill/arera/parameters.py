"""Parse ``PO_Parametri_Mercato_Libero_E_{date}.csv`` (mercato libero) and
``PO_Parametri_E_{date}.csv`` (PLACET): ``nome_parametro,valore,descrizione``.

These files carry the numeric values (msd, modeol, uniess, terna, capprod,
interr, cpty_mrkt_1..3, dispbt_d, cdispd, rst, rstg, ...) needed to price
``TIPO_DISPACCIAMENTO`` codes -- see ``bestbill.arera.policy`` for how they
combine into an offer's dispatching cost, and docs/arera-data.md for the
download URLs and publication schedule.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

_REQUIRED_COLUMNS = {"nome_parametro", "valore"}


class ParametersFormatError(ValueError):
    """The parameters CSV doesn't match the expected format."""


@dataclass(frozen=True)
class Parameters:
    """``nome_parametro -> valore``, plus descriptions kept for the
    manifest/provenance (never used in pricing decisions).
    """

    values: dict[str, float] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> float | None:
        return self.values.get(name)


def _decode(raw: bytes) -> str:
    for encoding in _ENCODINGS_TO_TRY:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParametersFormatError(
        "could not decode parameters CSV with any known encoding"
    )


def parse_parameters_text(text: str) -> Parameters:
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    if not _REQUIRED_COLUMNS.issubset(fieldnames):
        raise ParametersFormatError(
            f"missing required column(s), got {sorted(fieldnames)!r}"
        )
    values: dict[str, float] = {}
    descriptions: dict[str, str] = {}
    for row in reader:
        name = (row.get("nome_parametro") or "").strip()
        if not name:
            continue
        raw_value = (row.get("valore") or "").strip()
        try:
            values[name] = float(raw_value)
        except ValueError as exc:
            raise ParametersFormatError(
                f"parameter {name!r} has a non-numeric value: {raw_value!r}"
            ) from exc
        descriptions[name] = (row.get("descrizione") or "").strip()
    if not values:
        raise ParametersFormatError("no parameter rows found")
    return Parameters(values=values, descriptions=descriptions)


def parse_parameters_bytes(raw: bytes) -> Parameters:
    return parse_parameters_text(_decode(raw))


def parse_parameters_file(path: str) -> Parameters:
    with open(path, "rb") as f:
        raw = f.read()
    return parse_parameters_bytes(raw)
