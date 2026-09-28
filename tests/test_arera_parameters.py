import pathlib

import pytest

from bestbill.arera.parameters import (
    ParametersFormatError,
    parse_parameters_bytes,
    parse_parameters_file,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "arera" / "params_ml.csv"


def test_parse_parameters_file_has_expected_values():
    params = parse_parameters_file(str(FIXTURE))
    assert params.get("msd") == pytest.approx(0.003659)
    assert params.get("cdispd") == pytest.approx(0.024)
    assert params.get("dispbt_d") == pytest.approx(1.107)
    assert params.get("missing-parameter") is None


def test_parse_parameters_keeps_descriptions():
    params = parse_parameters_file(str(FIXTURE))
    assert "dispacciamento" in params.descriptions["cdispd"].lower()


def test_parse_parameters_missing_column_raises():
    with pytest.raises(ParametersFormatError):
        parse_parameters_bytes(b"a,b\n1,2\n")


def test_parse_parameters_non_numeric_value_raises():
    with pytest.raises(ParametersFormatError):
        parse_parameters_bytes(b"nome_parametro,valore,descrizione\nfoo,abc,desc\n")


def test_parse_parameters_empty_raises():
    with pytest.raises(ParametersFormatError):
        parse_parameters_bytes(b"nome_parametro,valore,descrizione\n")


def test_parse_parameters_decode_falls_back_to_cp1252():
    raw = "nome_parametro,valore,descrizione\nfoo,1.5,città\n".encode("cp1252")
    params = parse_parameters_bytes(raw)
    assert params.get("foo") == 1.5
