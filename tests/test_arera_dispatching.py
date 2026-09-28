"""Focused coverage for dispatching, Maggior Tutela exclusion, and the
IVA/percent discount rules, using small hand-built ``<offerta>`` XML
fragments (rather than the large real-data fixture) so each case is easy
to read and to hand-verify against docs/pricing-policy.md.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

import pytest

from bestbill.arera.mlibero import Excluded, parse_offerta
from bestbill.arera.parameters import parse_parameters_file
from bestbill.core.models import Offer

_NS = "http://www.acquirenteunico.it/schemas/SII_AU/OffertaRetail/01"

PARAMS = parse_parameters_file(
    str(pathlib.Path(__file__).parent / "fixtures" / "arera" / "params_ml.csv")
)


def _disp_xml(codes: list[tuple[str, float | None]]) -> str:
    rows = []
    for code, valore in codes:
        valore_xml = (
            f"<VALORE_DISP>{valore}</VALORE_DISP>" if valore is not None else ""
        )
        rows.append(
            f"<Dispacciamento><TIPO_DISPACCIAMENTO>{code}</TIPO_DISPACCIAMENTO>"
            f"{valore_xml}</Dispacciamento>"
        )
    return "".join(rows)


def _offerta_xml(
    *,
    cod_offerta: str = "TEST01",
    tipo_offerta: str = "02",
    idx: str = "12",
    dispacciamenti: list[tuple[str, float | None]] | None = None,
    extra_sconti: str = "",
    fixed_fee: float = 100.0,
) -> str:
    if dispacciamenti is None:
        dispacciamenti = [("14", None)]
    idx_block = (
        f"<RiferimentiPrezzoEnergia><IDX_PREZZO_ENERGIA>{idx}"
        "</IDX_PREZZO_ENERGIA></RiferimentiPrezzoEnergia>"
        if tipo_offerta == "02"
        else ""
    )
    energy_component = (
        "<ComponenteImpresa><MACROAREA>04</MACROAREA>"
        "<IntervalloPrezzi><PREZZO>0.02</PREZZO><UNITA_MISURA>03</UNITA_MISURA>"
        "</IntervalloPrezzi></ComponenteImpresa>"
        if tipo_offerta == "02"
        else "<ComponenteImpresa><MACROAREA>06</MACROAREA>"
        "<IntervalloPrezzi><PREZZO>0.15</PREZZO><UNITA_MISURA>03</UNITA_MISURA>"
        "</IntervalloPrezzi></ComponenteImpresa>"
    )
    return f"""<offerta xmlns="{_NS}">
        <IdentificativiOfferta>
            <PIVA_UTENTE>12345678901</PIVA_UTENTE>
            <COD_OFFERTA>{cod_offerta}</COD_OFFERTA>
        </IdentificativiOfferta>
        <DettaglioOfferta>
            <TIPO_CLIENTE>01</TIPO_CLIENTE>
            <OFFERTA_SINGOLA>SI</OFFERTA_SINGOLA>
            <TIPO_OFFERTA>{tipo_offerta}</TIPO_OFFERTA>
            <NOME_OFFERTA>Offerta di test</NOME_OFFERTA>
        </DettaglioOfferta>
        {idx_block}
        <TipoPrezzo><TIPOLOGIA_FASCE>01</TIPOLOGIA_FASCE></TipoPrezzo>
        {_disp_xml(dispacciamenti)}
        {energy_component}
        <ComponenteImpresa><MACROAREA>01</MACROAREA>
            <IntervalloPrezzi><PREZZO>{fixed_fee}</PREZZO>
            <UNITA_MISURA>01</UNITA_MISURA></IntervalloPrezzi>
        </ComponenteImpresa>
        {extra_sconti}
    </offerta>"""


def _parse(xml_text: str, params=PARAMS):
    el = ET.fromstring(xml_text)  # noqa: S314
    return parse_offerta(el, params)


# --- Dispatching codes ------------------------------------------------


def test_dispatching_code_01_is_cdisp_with_losses():
    offer = _parse(_offerta_xml(dispacciamenti=[("01", None)]))
    assert isinstance(offer, Offer)
    expected = (0.003659 + 0.001339 + 0.003346 + 0.000717 + 0.0 + 0.002490) * 1.10
    assert offer.dispatching_eur_kwh == pytest.approx(expected)
    assert offer.dispatching_eur_year == 0.0
    assert not offer.dispatching_approximate


@pytest.mark.parametrize(
    ("code", "param_name"),
    [
        ("03", "msd"),
        ("04", "modeol"),
        ("05", "uniess"),
        ("06", "terna"),
        ("07", "capprod"),
        ("08", "interr"),
    ],
)
def test_dispatching_individual_codes_apply_losses(code, param_name):
    offer = _parse(_offerta_xml(dispacciamenti=[(code, None)]))
    assert isinstance(offer, Offer)
    assert offer.dispatching_eur_kwh == pytest.approx(PARAMS.get(param_name) * 1.10)


def test_dispatching_code_09_is_capacity_market_mean_flagged_approximate():
    offer = _parse(_offerta_xml(dispacciamenti=[("09", None)]))
    assert isinstance(offer, Offer)
    mean_value = (
        sum(PARAMS.get(n) for n in ("cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3")) / 3
    )
    assert offer.dispatching_eur_kwh == pytest.approx(mean_value)
    assert offer.dispatching_approximate


def test_dispatching_code_13_is_fixed_fee_no_losses():
    offer = _parse(_offerta_xml(dispacciamenti=[("13", None)]))
    assert isinstance(offer, Offer)
    assert offer.dispatching_eur_year == pytest.approx(PARAMS.get("dispbt_d"))
    assert offer.dispatching_eur_kwh == 0.0


def test_dispatching_code_14_is_cdispd_no_losses():
    offer = _parse(_offerta_xml(dispacciamenti=[("14", None)]))
    assert isinstance(offer, Offer)
    assert offer.dispatching_eur_kwh == pytest.approx(PARAMS.get("cdispd"))


def test_dispatching_code_99_uses_valore_disp():
    offer = _parse(_offerta_xml(dispacciamenti=[("99", 0.0123)]))
    assert isinstance(offer, Offer)
    assert offer.dispatching_eur_kwh == pytest.approx(0.0123)


def test_dispatching_code_99_missing_valore_disp_excluded():
    result = _parse(_offerta_xml(dispacciamenti=[("99", None)]))
    assert isinstance(result, Excluded)
    assert "VALORE_DISP" in result.reason


def test_dispatching_unknown_code_excluded():
    result = _parse(_offerta_xml(dispacciamenti=[("42", None)]))
    assert isinstance(result, Excluded)
    assert "non supportato" in result.reason


def test_dispatching_missing_parameter_excluded():
    from bestbill.arera.parameters import Parameters

    params_without_msd = Parameters(
        values={k: v for k, v in PARAMS.values.items() if k != "msd"},
        descriptions=PARAMS.descriptions,
    )
    result = _parse(
        _offerta_xml(dispacciamenti=[("03", None)]), params=params_without_msd
    )
    assert isinstance(result, Excluded)
    assert "msd" in result.reason


def test_dispatching_codes_11_12_excluded_on_domestic_offer():
    for code in ("11", "12"):
        result = _parse(_offerta_xml(dispacciamenti=[(code, None)]))
        assert isinstance(result, Excluded), code
        assert "non domestiche" in result.reason


def test_dispatching_additive_combo_01_09_13():
    offer = _parse(
        _offerta_xml(dispacciamenti=[("01", None), ("09", None), ("13", None)])
    )
    assert isinstance(offer, Offer)
    cdisp = (0.003659 + 0.001339 + 0.003346 + 0.000717 + 0.0 + 0.002490) * 1.10
    mean_cpty = (
        sum(PARAMS.get(n) for n in ("cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3")) / 3
    )
    assert offer.dispatching_eur_kwh == pytest.approx(cdisp + mean_cpty)
    assert offer.dispatching_eur_year == pytest.approx(PARAMS.get("dispbt_d"))
    assert offer.dispatching_approximate


def test_dispatching_additive_combo_individual_codes_plus_09_13():
    codes = [
        ("03", None),
        ("04", None),
        ("05", None),
        ("06", None),
        ("07", None),
        ("08", None),
        ("09", None),
        ("13", None),
    ]
    offer = _parse(_offerta_xml(dispacciamenti=codes))
    assert isinstance(offer, Offer)
    individual_sum = (
        sum(
            PARAMS.get(n)
            for n in ("msd", "modeol", "uniess", "terna", "capprod", "interr")
        )
        * 1.10
    )
    mean_cpty = (
        sum(PARAMS.get(n) for n in ("cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3")) / 3
    )
    assert offer.dispatching_eur_kwh == pytest.approx(individual_sum + mean_cpty)
    assert offer.dispatching_eur_year == pytest.approx(PARAMS.get("dispbt_d"))


def test_cdispd_identity_matches_cdisp_plus_mean_cpty():
    from bestbill.arera import policy

    diff = policy.dispatching_identity_diff(PARAMS)
    assert diff is not None
    assert abs(diff) <= policy.DISPATCHING_IDENTITY_TOLERANCE


# --- Maggior Tutela exclusions -----------------------------------------


def test_maggior_tutela_idx_05_excluded():
    result = _parse(_offerta_xml(idx="05"))
    assert isinstance(result, Excluded)
    assert result.reason == "riferita a Maggior Tutela"


def test_maggior_tutela_dispatching_02_excluded():
    result = _parse(_offerta_xml(dispacciamenti=[("02", None)]))
    assert isinstance(result, Excluded)
    assert result.reason == "riferita a Maggior Tutela"


def test_maggior_tutela_dispatching_10_excluded():
    result = _parse(_offerta_xml(dispacciamenti=[("10", None)]))
    assert isinstance(result, Excluded)
    assert result.reason == "riferita a Maggior Tutela"


def test_maggior_tutela_sconto_tipologia_04_excluded():
    sconto = """<Sconto>
        <NOME>Sconto MT</NOME>
        <VALIDITA>02</VALIDITA>
        <IVA_SCONTO>01</IVA_SCONTO>
        <Condizione><CONDIZIONE_APPLICAZIONE>00</CONDIZIONE_APPLICAZIONE></Condizione>
        <PrezziSconto><TIPOLOGIA>04</TIPOLOGIA><UNITA_MISURA>01</UNITA_MISURA>
        <PREZZO>10</PREZZO></PrezziSconto>
    </Sconto>"""
    result = _parse(_offerta_xml(extra_sconti=sconto))
    assert isinstance(result, Excluded)
    assert result.reason == "riferita a Maggior Tutela"


# --- Discounts: IVA conversion and unconditional discount --------------


def test_discount_iva_sconto_02_converts_nominal_to_pre_vat():
    sconto = """<Sconto>
        <NOME>Sconto post-IVA</NOME>
        <VALIDITA>02</VALIDITA>
        <IVA_SCONTO>02</IVA_SCONTO>
        <Condizione><CONDIZIONE_APPLICAZIONE>00</CONDIZIONE_APPLICAZIONE></Condizione>
        <PrezziSconto><TIPOLOGIA>01</TIPOLOGIA><UNITA_MISURA>01</UNITA_MISURA>
        <PREZZO>11</PREZZO></PrezziSconto>
    </Sconto>"""
    offer = _parse(_offerta_xml(extra_sconti=sconto))
    assert isinstance(offer, Offer)
    assert len(offer.discounts) == 1
    assert offer.discounts[0].amount == pytest.approx(11 / 1.10)


def test_discount_iva_sconto_01_kept_as_is():
    sconto = """<Sconto>
        <NOME>Sconto pre-IVA</NOME>
        <VALIDITA>02</VALIDITA>
        <IVA_SCONTO>01</IVA_SCONTO>
        <Condizione><CONDIZIONE_APPLICAZIONE>00</CONDIZIONE_APPLICAZIONE></Condizione>
        <PrezziSconto><TIPOLOGIA>01</TIPOLOGIA><UNITA_MISURA>01</UNITA_MISURA>
        <PREZZO>10</PREZZO></PrezziSconto>
    </Sconto>"""
    offer = _parse(_offerta_xml(extra_sconti=sconto))
    assert isinstance(offer, Offer)
    assert offer.discounts[0].amount == pytest.approx(10.0)
    assert not offer.discounts[0].conditional
