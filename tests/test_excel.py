import pathlib

import pytest

from bestbill.io.excel import (
    ExcelFormatError,
    list_locations,
    read_custom_offers,
    read_location_data,
)

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "src" / "bestbill" / "data" / "sample.xlsx"
)


def test_list_locations_finds_storico_sheets():
    assert list_locations(SAMPLE) == ["Esempio"]


def test_read_custom_offers_from_sample():
    offers = read_custom_offers(SAMPLE)
    assert len(offers) == 6
    names = {o.name for o in offers}
    assert "Alfa Energia Fissa" in names
    assert "Beta Luce Variabile" in names
    variable_offers = [o for o in offers if o.price_type.value == "variable"]
    fixed_offers = [o for o in offers if o.price_type.value == "fixed"]
    assert len(variable_offers) == 3
    assert len(fixed_offers) == 3


def test_read_location_data_from_sample():
    profile, actual, forecast = read_location_data(SAMPLE, "Esempio")
    assert len(profile.months) == 12
    assert profile.total_kwh == pytest.approx(2700.0)
    assert not actual.is_empty
    assert not forecast.is_empty
    # Forecast PUN is flat at 0.12 for every month in the sample.
    assert all(v == pytest.approx(0.12) for v in forecast.values.values())


def test_read_location_data_unknown_location_raises_clear_error():
    with pytest.raises(ExcelFormatError, match="Storico_Nowhere"):
        read_location_data(SAMPLE, "Nowhere")


def test_read_custom_offers_missing_sheet_raises(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "NotTariffario"
    path = tmp_path / "bad.xlsx"
    wb.save(path)

    with pytest.raises(ExcelFormatError, match="Tariffario"):
        read_custom_offers(path)


def test_read_custom_offers_missing_column_raises(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Tariffario"
    ws.append(["Tariffa", "Alpha [€/kWh]", "CCV [€]"])  # missing Prezzo fisso
    path = tmp_path / "bad.xlsx"
    wb.save(path)

    with pytest.raises(ExcelFormatError, match="missing column"):
        read_custom_offers(path)
