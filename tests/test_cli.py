from __future__ import annotations

import pytest

from kol_monitor.cli import build_parser, main


def test_parser_accepts_list_kols():
    args = build_parser().parse_args(["list-kols"])

    assert args.command == "list-kols"


def test_list_kols_outputs_62_handles(capsys):
    main(["list-kols"])

    out = capsys.readouterr().out
    assert "62 KOL" in out
    assert "168X_Fortune" in out
    assert "Franktradinglog" in out
    assert "golden_pan1" in out
    assert "rickawsb" in out
    assert "qinbafrank" in out
    assert "LeoYuen13" in out
    assert "crux_capital_" in out


def test_run_once_dry_run_is_accepted(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run-once", "--dry-run"])

    assert exc.value.code == 0
    assert "dry run" in capsys.readouterr().out.lower()
