"""Parse the ARERA "Ricerca operatori" export: the electricity-retailer
list published at https://www.arera.it/area-operatori/ricerca-operatori,
used to resolve mercato libero offers' supplier display name (the XML only
publishes ``PIVA_UTENTE``, see ``bestbill.arera.mlibero`` and
``bestbill.catalog.build``).

Data minimisation / licence: the export also carries addresses and contact
details, but this importer reads and keeps **only** ``RAGIONE SOCIALE``
(name), ``PARTITA IVA`` (VAT) and ``SITO WEB`` (website) -- see
``PROVENANCE.md``. The export is licensed CC BY-SA 4.0 (arera.it terms of
use, "Riuso dei dati pubblici (Open Data) e copyright").
"""

from __future__ import annotations

import io
import re
import urllib.parse
import zipfile
from dataclasses import dataclass

import openpyxl

#: The ricerca-operatori page links to the current export as
#: ``/fileadmin/ricercaoperatori/export-mercato-vend<DD_MM_YYYY_HH_MM_SS>.zip``;
#: the timestamp changes at every ARERA refresh.
_EXPORT_ZIP_HREF_RE = re.compile(
    r'href="(/fileadmin/ricercaoperatori/export-mercato-vend[^"]+\.zip)"'
)

ARERA_BASE_URL = "https://www.arera.it"
RICERCA_OPERATORI_URL = f"{ARERA_BASE_URL}/area-operatori/ricerca-operatori"

#: Columns this importer reads from Sheet1 -- see the module docstring for
#: why addresses/contacts (also present in the export) are never read.
_REQUIRED_COLUMNS = ("RAGIONE SOCIALE", "PARTITA IVA", "SITO WEB")

_VAT_LENGTH = 11


class OperatorsFormatError(ValueError):
    """The ARERA operators page/export doesn't match the expected format."""


@dataclass(frozen=True)
class Operator:
    """One ARERA-registered electricity retailer, name + VAT + website
    only (see the module docstring's data-minimisation note).
    """

    name: str
    website: str | None = None


def discover_export_url(html: str) -> str:
    """Find the current export zip URL on the ricerca-operatori page.
    Raises :class:`OperatorsFormatError` if the link isn't found (the page
    layout changed, or the fixture/response isn't the expected page).
    """
    match = _EXPORT_ZIP_HREF_RE.search(html)
    if match is None:
        raise OperatorsFormatError(
            "could not find the export-mercato-vend zip link on the "
            "ricerca-operatori page"
        )
    return f"{ARERA_BASE_URL}{match.group(1)}"


def zero_pad_vat(value: object) -> str:
    """Zero-pad a PARTITA IVA value to 11 digits. The xlsx column is
    typically text, but some rows/tools may store it as a number (in which
    case openpyxl hands back a ``float``/``int``, e.g. ``1244170526.0``).
    """
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    return text.zfill(_VAT_LENGTH)


def website_domain(url: str | None) -> str | None:
    """Strip scheme/``www.``/path from a website URL, e.g.
    ``"https://www.100energia.com/"`` -> ``"100energia.com"``. Returns
    ``None`` if ``url`` is empty or has no discernible host.
    """
    if not url:
        return None
    text = url.strip()
    if not text:
        return None
    candidate = text if "://" in text else f"//{text}"
    parsed = urllib.parse.urlsplit(candidate)
    host = parsed.netloc or parsed.path.split("/")[0]
    host = host.split("@")[-1].split(":")[0].lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def parse_operators_xlsx(raw: bytes) -> dict[str, Operator]:
    """Parse the export's ``Sheet1`` into ``PARTITA IVA -> Operator``
    (zero-padded to 11 digits). Rows missing a name or VAT are skipped.
    """
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None:
        raise OperatorsFormatError("the operators xlsx sheet is empty")
    index = {str(name).strip(): i for i, name in enumerate(header) if name is not None}
    missing = [c for c in _REQUIRED_COLUMNS if c not in index]
    if missing:
        raise OperatorsFormatError(
            f"operators xlsx is missing column(s) {missing}; found {list(index)}"
        )

    operators: dict[str, Operator] = {}
    for row in rows:
        if row is None or all(v is None for v in row):
            continue
        raw_name = row[index["RAGIONE SOCIALE"]]
        raw_vat = row[index["PARTITA IVA"]]
        raw_site = row[index["SITO WEB"]]
        if raw_name is None or raw_vat is None:
            continue
        name = str(raw_name).strip()
        if not name:
            continue
        vat = zero_pad_vat(raw_vat)
        website = str(raw_site).strip() if raw_site is not None else None
        operators[vat] = Operator(name=name, website=website or None)
    return operators


def parse_operators_zip(raw: bytes) -> dict[str, Operator]:
    """Extract the single ``.xlsx`` member of the export zip and parse it."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
        if not names:
            raise OperatorsFormatError("no .xlsx file found in the operators zip")
        xlsx_bytes = zf.read(names[0])
    return parse_operators_xlsx(xlsx_bytes)


def parse_operators_file(path: str) -> dict[str, Operator]:
    """Parse either a ``.zip`` export or a bare ``.xlsx`` file (``--operators
    <zip|xlsx>`` on ``bestbill catalog build``)."""
    with open(path, "rb") as f:
        raw = f.read()
    if path.lower().endswith(".zip"):
        return parse_operators_zip(raw)
    return parse_operators_xlsx(raw)
