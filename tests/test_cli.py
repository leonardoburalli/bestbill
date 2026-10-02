import pytest

from bestbill.cli import main


def test_no_args_prints_help(capsys):
    assert main([]) == 2
    assert "catalog" in capsys.readouterr().out


def test_compare_subcommand_is_gone():
    with pytest.raises(SystemExit) as exc:
        main(["compare", "--location", "x"])
    assert exc.value.code == 2


def test_catalog_without_subcommand_returns_error():
    assert main(["catalog"]) == 2
