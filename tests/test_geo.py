from bestbill.core.calculator import compare
from bestbill.core.models import ComuneRef, GeoRestriction
from bestbill.geo import get_comune, resolve_comune, search_comuni

from .helpers import fixed_offer, make_profile, make_pun

# Real ISTAT/ARERA codes: Genova (Liguria, regione 07, provincia 010),
# Torino (Piemonte, 01, 001), Milano (Lombardia, 03, 015).
GENOVA = "010025"
TORINO = "001272"
MILANO = "015146"


def test_get_comune_returns_hierarchy():
    c = get_comune(GENOVA)
    assert c is not None
    assert (c.nome, c.sigla_provincia, c.codice_provincia) == ("Genova", "GE", "010")
    assert (c.codice_regione, c.nome_regione) == ("07", "Liguria")


def test_provincia_code_is_comune_prefix_for_all_comuni():
    from bestbill.geo import _load

    assert all(c.codice_comune[:3] == c.codice_provincia for c in _load()[0].values())


def test_get_comune_unknown():
    assert get_comune("999999") is None


def test_resolve_unknown_comune_falls_back_to_provincia_prefix():
    ref = resolve_comune("999999")
    assert ref == ComuneRef(codice="999999", provincia="999", regione=None)


def test_search_is_accent_and_case_insensitive_prefix():
    names = [c.nome for c in search_comuni("agli")]
    assert "Agliè" in names
    assert all(n.casefold().startswith("agli") or "gli" in n for n in names)
    assert [c.nome for c in search_comuni("AGLIE")][0] == "Agliè"


def test_search_limit_empty_and_no_match():
    assert len(search_comuni("sa", limit=20)) == 20
    assert search_comuni("  ") == []
    assert search_comuni("zzzzzz") == []


def test_regione_only_restriction_matches_comune_in_region():
    geo = GeoRestriction(regioni=frozenset({"07"}))
    assert geo.matches(resolve_comune(GENOVA))
    assert not geo.matches(resolve_comune(MILANO))
    assert not geo.matches(resolve_comune("999999"))


def test_province_and_comune_restrictions_still_match():
    assert GeoRestriction(province=frozenset({"001"})).matches(resolve_comune(TORINO))
    assert GeoRestriction(comuni=frozenset({TORINO})).matches(resolve_comune(TORINO))
    assert not GeoRestriction(comuni=frozenset({TORINO})).matches(
        resolve_comune(MILANO)
    )


def test_compare_region_restricted_offer_eligibility():
    profile = make_profile([100.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(geo=GeoRestriction(regioni=frozenset({"07"})))

    inside = compare([offer], profile, pun, istat_comune=GENOVA)
    outside = compare([offer], profile, pun, istat_comune=MILANO)

    assert len(inside.results) == 1
    assert outside.excluded == [
        (offer.id, "offerta non disponibile nel comune indicato")
    ]
