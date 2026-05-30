from __future__ import annotations

import pytest

from kol_monitor.cli import build_parser, main


def test_parser_accepts_list_kols():
    args = build_parser().parse_args(["list-kols"])

    assert args.command == "list-kols"


def test_list_kols_outputs_54_handles(capsys):
    main(["list-kols"])

    out = capsys.readouterr().out
    assert "54 KOL" in out
    assert "qinbafrank" in out


def test_run_once_dry_run_is_accepted(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run-once", "--dry-run"])

    assert exc.value.code == 0
    assert "dry run" in capsys.readouterr().out.lower()
