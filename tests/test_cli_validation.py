"""
Validação dos novos flags do CLI: --filepath-format, --parpar-args,
--rename-extensionless. Asserts via parse_args().
"""
import shlex

import pytest

from upapasta.cli import parse_args


def _run_parse(argv, monkeypatch):
    monkeypatch.setattr("sys.argv", ["upapasta"] + argv)
    return parse_args()


def test_filepath_format_default_is_common(monkeypatch):
    args = _run_parse(["some/path"], monkeypatch)
    assert args.filepath_format == "common"


@pytest.mark.parametrize("fmt", ["common", "keep", "basename", "outrel"])
def test_filepath_format_accepts_valid(monkeypatch, fmt):
    args = _run_parse(["some/path", "--filepath-format", fmt], monkeypatch)
    assert args.filepath_format == fmt


def test_filepath_format_rejects_invalid(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["upapasta", "x", "--filepath-format", "nope"])
    with pytest.raises(SystemExit):
        parse_args()


def test_parpar_args_passthrough(monkeypatch):
    args = _run_parse(
        ["some/path", "--parpar-args", "--noindex --foo=bar"], monkeypatch
    )
    # O atributo deve existir e ser tokenizável via shlex
    tokens = shlex.split(args.parpar_args)
    assert tokens == ["--noindex", "--foo=bar"]


def test_rename_extensionless_default_off(monkeypatch):
    args = _run_parse(["some/path"], monkeypatch)
    assert args.rename_extensionless is False


def test_rename_extensionless_flag(monkeypatch):
    args = _run_parse(["some/path", "--rename-extensionless"], monkeypatch)
    assert args.rename_extensionless is True
