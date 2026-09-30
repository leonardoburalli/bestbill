"""ISTAT comuni table: comune -> provincia -> regione, and name search.

Data: ``bestbill/data/comuni.csv`` (built by ``scripts/make_comuni.py`` from
the ISTAT "Elenco comuni italiani", CC BY 4.0).
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from functools import cache
from importlib import resources

from bestbill.core.models import ComuneRef

__all__ = ["Comune", "get_comune", "resolve_comune", "search_comuni"]


@dataclass(frozen=True)
class Comune:
    codice_comune: str
    nome: str
    sigla_provincia: str
    codice_provincia: str
    codice_regione: str
    nome_regione: str

    def ref(self) -> ComuneRef:
        return ComuneRef(
            codice=self.codice_comune,
            provincia=self.codice_provincia,
            regione=self.codice_regione,
        )


def _fold(text: str) -> str:
    """Lower-case and strip accents/apostrophe variants for matching."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace(
        "'", " "
    )


@cache
def _load() -> tuple[dict[str, Comune], list[tuple[str, Comune]]]:
    text = resources.files("bestbill").joinpath("data/comuni.csv").read_text("utf-8")
    by_code: dict[str, Comune] = {}
    for row in csv.DictReader(text.splitlines()):
        c = Comune(**row)
        by_code[c.codice_comune] = c
    by_name = sorted(((_fold(c.nome), c) for c in by_code.values()), key=lambda t: t[0])
    return by_code, by_name


def get_comune(code: str) -> Comune | None:
    return _load()[0].get(code)


def resolve_comune(code: str) -> ComuneRef:
    """Comune reference for a 6-digit ISTAT code. Unknown codes fall back to
    the provincia derived from the first 3 digits (no regione).
    """
    known = get_comune(code)
    if known is not None:
        return known.ref()
    return ComuneRef(codice=code, provincia=code[:3], regione=None)


def search_comuni(query: str, limit: int = 20) -> list[Comune]:
    """Comuni whose name starts with ``query`` (accent/case-insensitive),
    prefix matches first in alphabetical order.
    """
    q = _fold(query.strip())
    if not q:
        return []
    out = [c for name, c in _load()[1] if name.startswith(q)]
    return out[:limit]
