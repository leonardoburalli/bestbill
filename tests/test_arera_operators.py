import pathlib

import pytest

from bestbill.arera.operators import (
    ARERA_BASE_URL,
    OperatorsFormatError,
    discover_export_url,
    parse_operators_xlsx,
    parse_operators_zip,
    website_domain,
    zero_pad_vat,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "arera"


def test_discover_export_url_finds_the_zip_link():
    html = (FIXTURES / "ricerca_operatori.html").read_text(encoding="utf-8")
    url = discover_export_url(html)
    assert url == (
        f"{ARERA_BASE_URL}/fileadmin/ricercaoperatori/"
        "export-mercato-vend21_09_2026_09_35_02.zip"
    )


def test_discover_export_url_raises_when_not_found():
    with pytest.raises(OperatorsFormatError):
        discover_export_url("<html><body>no link here</body></html>")


def test_parse_operators_xlsx_reads_name_vat_site_only():
    raw = (FIXTURES / "operators.xlsx").read_bytes()
    operators = parse_operators_xlsx(raw)

    assert operators["01244170526"].name == "+Energia"
    assert operators["01244170526"].website == "http://www.piuenergia.it"
    assert operators["08985501215"].name == "100ENERGIA S.R.L."


def test_parse_operators_xlsx_zero_pads_numeric_vat():
    raw = (FIXTURES / "operators.xlsx").read_bytes()
    operators = parse_operators_xlsx(raw)

    assert "12345678901" in operators
    assert operators["12345678901"].name == "ACME ENERGIA SPA"
    assert operators["12345678901"].website is None


def test_parse_operators_xlsx_strips_trailing_spaces_from_name():
    raw = (FIXTURES / "operators.xlsx").read_bytes()
    operators = parse_operators_xlsx(raw)

    assert operators["01244170526"].name == "+Energia"
    assert not operators["01244170526"].name.endswith(" ")


def test_parse_operators_xlsx_missing_required_column_raises():
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["RAGIONE SOCIALE", "PARTITA IVA"])  # missing SITO WEB
    ws.append(["Foo", "00000000000"])
    buf = io.BytesIO()
    wb.save(buf)

    with pytest.raises(OperatorsFormatError):
        parse_operators_xlsx(buf.getvalue())


def test_parse_operators_zip_extracts_the_single_xlsx(tmp_path):
    import zipfile

    xlsx_bytes = (FIXTURES / "operators.xlsx").read_bytes()
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("export-mercato-vend21_09_2026_09_35_02.xlsx", xlsx_bytes)

    operators = parse_operators_zip(zip_path.read_bytes())
    assert operators["01244170526"].name == "+Energia"


def test_zero_pad_vat_string():
    assert zero_pad_vat("123") == "00000000123"
    assert zero_pad_vat("12345678901") == "12345678901"


def test_zero_pad_vat_numeric():
    assert zero_pad_vat(1244170526.0) == "01244170526"
    assert zero_pad_vat(1244170526) == "01244170526"


def test_website_domain_strips_scheme_www_and_path():
    assert website_domain("https://www.100energia.com/") == "100energia.com"
    assert website_domain("http://rubinoenergas.it/index.html") == "rubinoenergas.it"
    assert website_domain("www.example.com") == "example.com"
    assert website_domain("example.com") == "example.com"


def test_website_domain_handles_missing_or_empty():
    assert website_domain(None) is None
    assert website_domain("") is None
    assert website_domain("   ") is None
