import pathlib

import pytest

from bestbill.arera.indices import (
    IndicesFormatError,
    parse_indices_bytes,
    parse_indices_file,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "arera" / "indices.csv"


def test_indices_fixture_parses_at_least_twelve_months():
    series = parse_indices_file(str(FIXTURE))
    assert len(series.values) >= 12


def test_indices_decimal_comma_and_semicolon():
    raw = "AnnoMese;PUN\n202001;0,047470\n".encode("cp1252")
    series = parse_indices_bytes(raw)
    from datetime import date

    assert series.values[date(2020, 1, 1)] == pytest.approx(0.04747)


def test_indices_handles_cp1252_euro_sign_in_header():
    raw = "AnnoMese;PUN (\u20ac/kWh)\n202001;0,047470\n".encode("cp1252")
    series = parse_indices_bytes(raw)
    from datetime import date

    assert series.values[date(2020, 1, 1)] == pytest.approx(0.04747)


def test_indices_handles_utf8():
    raw = "AnnoMese;PUN (\u20ac/kWh)\n202001;0,047470\n".encode("utf-8")
    series = parse_indices_bytes(raw)
    from datetime import date

    assert series.values[date(2020, 1, 1)] == pytest.approx(0.04747)


def test_indices_rejects_empty_file():
    with pytest.raises(IndicesFormatError):
        parse_indices_bytes(b"")


def test_indices_rejects_bad_month():
    with pytest.raises(IndicesFormatError):
        parse_indices_bytes(b"AnnoMese;PUN\n2020XX;0,05\n")
