"""Tests CLI légers (pas de démon Docker)."""
from __future__ import annotations

import string

from typer.testing import CliRunner

from pentbox import __version__, cli


def test_gen_vnc_password_length_and_charset():
    pw = cli._gen_vnc_password()
    assert len(pw) == 8
    assert set(pw) <= set(string.ascii_letters + string.digits)


def test_gen_vnc_password_varies():
    # 5 tirages aléatoires ne peuvent pas tous être identiques en pratique.
    assert len({cli._gen_vnc_password() for _ in range(5)}) > 1


def test_version_flag_outputs_version():
    result = CliRunner().invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_no_args_shows_help_not_crash():
    # no_args_is_help=True → aide affichée, sortie non nulle mais pas de traceback.
    result = CliRunner().invoke(cli.app, [])
    assert "pentbox" in result.output.lower()
    assert result.exception is None or isinstance(result.exception, SystemExit)
