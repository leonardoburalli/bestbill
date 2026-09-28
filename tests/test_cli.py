import pathlib

from bestbill.cli import main

SAMPLE = (
    pathlib.Path(__file__).parent.parent / "src" / "bestbill" / "data" / "sample.xlsx"
)


def test_cli_end_to_end_writes_csv(tmp_path, capsys):
    output_dir = tmp_path / "out"
    exit_code = main(
        [
            "--file",
            str(SAMPLE),
            "--location",
            "Esempio",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert exit_code == 0

    csv_files = list(output_dir.glob("*_Esempio_comparison.csv"))
    assert len(csv_files) == 1
    content = csv_files[0].read_text(encoding="utf-8")
    assert content.startswith("# Stima nell'ipotesi")
    assert "rank,supplier,name,price_type" in content

    captured = capsys.readouterr()
    assert "Confronto offerte per: Esempio" in captured.out
    assert "Non è una previsione." in captured.out


def test_cli_unknown_location_returns_error_code(tmp_path):
    exit_code = main(
        [
            "--file",
            str(SAMPLE),
            "--location",
            "Nowhere",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 2


def test_cli_missing_file_returns_error_code(tmp_path):
    exit_code = main(
        [
            "--file",
            str(tmp_path / "does-not-exist.xlsx"),
            "--location",
            "Esempio",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 1
