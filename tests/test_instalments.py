"""Bonuses paid in instalments: parser, importer, calculator, API."""

from __future__ import annotations

import pytest

from bestbill.arera import policy
from bestbill.arera.mlibero import Excluded
from bestbill.catalog.store import offer_from_json
from bestbill.core.calculator import compare
from bestbill.core.models import Discount, DiscountUnit, DiscountValidity, Offer

from .helpers import fixed_offer, make_profile, make_pun
from .test_arera_dispatching import _offerta_xml, _parse

MIA_FISSA = (
    "Per tutti i Clienti che sottoscrivano la presente offerta è previsto uno "
    "sconto mensile pari a 4,17 euro/mese per un totale di 36 mesi pari alla "
    "durata delle presenti condizioni economiche."
)


@pytest.mark.parametrize(
    ("text", "months", "amount", "every"),
    [
        (MIA_FISSA, 36, 4.17, 1),
        ("Bonus mensile di 4 Euro per 48 mesi con l'acquisto", 48, 4.0, 1),
        ("erogato in quote mensili da 6 € per i primi 48 mesi", 48, 6.0, 1),
        ("bonus mensile di € 5,0 per i primi 36 mesi", 36, 5.0, 1),
        ("riconosciuto in 24 rate pari a 6 €/mese ciascuna", 24, 6.0, 1),
        ("suddiviso in 3 bonus annuali da 10 euro", 36, 10.0, 12),
        ("suddiviso in 4 bonus da 10 € erogati ogni 6 mesi", 24, 10.0, 6),
    ],
)
def test_parse_instalments_positive(text, months, amount, every):
    info = policy.parse_instalments(text)
    assert info == policy.InstalmentInfo(months, amount, every)


@pytest.mark.parametrize(
    "text",
    [
        "L'accredito del Bonus una tantum di 10,00 euro entro sei mesi dalla data",
        "Sconto percentuale su Corrispettivo annuo, 12% per i primi 6 mesi",
        "suddiviso in 3 bonus da 10 euro accreditati nella bolletta del 1°, 6°, 12°",
        "L'offerta garantisce un Bonus di 4,17€/mese per ogni mese di permanenza",
        "",
    ],
)
def test_parse_instalments_negative(text):
    assert policy.parse_instalments(text) is None


def test_resolve_requires_total_to_match_and_long_plan():
    one_off = DiscountUnit.EUR_ONE_OFF
    assert policy.resolve_instalments(MIA_FISSA, one_off, 150.0, 150.0) is not None
    # declared total doesn't match instalment x count -> not spread
    assert policy.resolve_instalments(MIA_FISSA, one_off, 50.0, 50.0) is None
    # plan within 12 months -> nothing to spread
    assert policy.resolve_instalments("5 €/mese per 12 mesi", one_off, 60, 60) is None
    # other units are never spread
    assert policy.resolve_instalments(MIA_FISSA, DiscountUnit.PERCENT, 150, 150) is None


def test_resolve_scales_instalment_with_vat_factor():
    info = policy.resolve_instalments(
        MIA_FISSA, DiscountUnit.EUR_ONE_OFF, 150.0, 150.0 / 1.10
    )
    assert info is not None
    assert info.amount == pytest.approx(4.17 / 1.10, rel=1e-4)


def _sconto(description: str, unit: str = "05", prezzo: str = "150", cond="00") -> str:
    return f"""<Sconto>
        <NOME>Bonus Fornitura</NOME><DESCRIZIONE>{description}</DESCRIZIONE>
        <VALIDITA>02</VALIDITA><IVA_SCONTO>01</IVA_SCONTO>
        <Condizione><CONDIZIONE_APPLICAZIONE>{cond}</CONDIZIONE_APPLICAZIONE></Condizione>
        <PrezziSconto><TIPOLOGIA>01</TIPOLOGIA><UNITA_MISURA>{unit}</UNITA_MISURA>
        <PREZZO>{prezzo}</PREZZO></PrezziSconto></Sconto>"""


def test_importer_stores_instalments():
    offer = _parse(_offerta_xml(extra_sconti=_sconto(MIA_FISSA)))
    assert isinstance(offer, Offer)
    d = offer.discounts[0]
    assert d.amount == 150.0
    assert (
        d.instalment_months,
        d.instalment_amount_eur,
        d.instalment_every_months,
    ) == (
        36,
        pytest.approx(4.17),
        1,
    )


def test_importer_leaves_conditional_and_ambiguous_alone():
    for xml in (
        _sconto(MIA_FISSA, cond="01"),
        _sconto("bonus entro sei mesi dall'attivazione"),
        _sconto(MIA_FISSA, prezzo="50"),
    ):
        offer = _parse(_offerta_xml(extra_sconti=xml))
        assert not isinstance(offer, Excluded)
        assert offer.discounts[0].instalment_months is None


def _discount(**kw) -> Discount:
    base = {
        "name": "Mia Fissa",
        "validity": DiscountValidity.WITHIN_12_MONTHS,
        "conditional": False,
        "amount": 150.0,
        "unit": DiscountUnit.EUR_ONE_OFF,
    }
    base.update(kw)
    return Discount(**base)


def test_first_12_months_value():
    d = _discount(instalment_months=36, instalment_amount_eur=4.17)
    assert policy.discount_annual_value_eur(d, 3000, 0) == pytest.approx(50.04)
    # capped by declared total
    d = _discount(amount=30.0, instalment_months=24, instalment_amount_eur=5.0)
    assert policy.discount_annual_value_eur(d, 3000, 0) == pytest.approx(30.0)
    # annual cadence: one instalment in the first 12 months
    d = _discount(
        instalment_months=36, instalment_amount_eur=50.0, instalment_every_months=12
    )
    assert policy.discount_annual_value_eur(d, 3000, 0) == pytest.approx(50.0)
    # no instalment info -> full declared amount
    assert policy.discount_annual_value_eur(_discount(), 3000, 0) == 150.0


def test_old_catalogue_json_loads_with_defaults():
    offer = fixed_offer(discounts=[_discount()])
    raw = offer.model_dump(mode="json")
    for key in (
        "instalment_months",
        "instalment_amount_eur",
        "instalment_every_months",
    ):
        del raw["discounts"][0][key]
    import json

    loaded = offer_from_json(json.dumps(raw))
    d = loaded.discounts[0]
    assert d.instalment_months is None
    assert d.instalment_amount_eur is None
    assert d.instalment_every_months == 1


def test_compare_credits_only_first_12_months_and_lists_applied():
    profile = make_profile([300.0] * 12)
    pun = make_pun([0.10] * 12)
    plain = fixed_offer("a", fee=0.0)
    spread = fixed_offer(
        "b",
        fee=0.0,
        discounts=[_discount(instalment_months=36, instalment_amount_eur=4.17)],
    )
    cond = fixed_offer(
        "c", fee=0.0, discounts=[_discount(conditional=True, amount=99.0)]
    )
    res = {r.offer_id: r for r in compare([plain, spread, cond], profile, pun).results}
    assert res["b"].breakdown.discounts == pytest.approx(50.04)
    assert res["b"].cost_eur == pytest.approx(res["a"].cost_eur - 50.04)
    (ad,) = res["b"].applied_discounts
    assert ad.amount_in_estimate_eur == pytest.approx(50.04)
    assert ad.declared_amount_eur == 150.0
    assert ad.instalment_months == 36
    assert ad.instalment_amount_eur == pytest.approx(4.17)
    assert res["a"].applied_discounts == []
    assert res["c"].applied_discounts == []


def test_applied_discounts_sum_matches_breakdown():
    profile = make_profile([300.0] * 12)
    pun = make_pun([0.10] * 12)
    offer = fixed_offer(
        "x",
        discounts=[
            _discount(instalment_months=36, instalment_amount_eur=4.17),
            _discount(name="pct", unit=DiscountUnit.PERCENT, amount=5.0),
            _discount(name="kwh", unit=DiscountUnit.EUR_KWH, amount=0.01),
        ],
    )
    (r,) = compare([offer], profile, pun).results
    assert len(r.applied_discounts) == 3
    total = sum(a.amount_in_estimate_eur for a in r.applied_discounts)
    assert total == pytest.approx(r.breakdown.discounts, abs=0.01)
    pct = next(a for a in r.applied_discounts if a.name == "pct")
    assert pct.declared_amount_eur is None
