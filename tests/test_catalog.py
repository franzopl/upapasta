"""Testes para catalog.py: detecção de categoria, registro e hook pós-upload."""

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from upapasta.catalog import detect_category, record_upload, run_post_upload_hook


# ── detect_category ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    # TV — padrão SxxExx
    ("Breaking.Bad.S01E01.Pilot.mkv",           "TV"),
    ("the.office.s03e04.hdtv.avi",              "TV"),
    ("Game.of.Thrones.S08E06.1080p.mkv",        "TV"),
    # TV — outros padrões
    ("Chernobyl.1x01.720p.mkv",                 "TV"),
    ("Doctor.Who.Season.2.Complete.mkv",        "TV"),
    # Anime
    ("[SubGroup] Naruto - 42 [720p].mkv",       "Anime"),
    ("[HorribleSubs] Attack on Titan - 01 [1080p].mkv", "Anime"),
    # Filme — ano no nome
    ("Wuthering.Heights.2026.1080p.BluRay.mkv", "Movie"),
    ("Dune.Part.Two.2024.mkv",                  "Movie"),
    ("The.Godfather.1972.Remastered.mkv",       "Movie"),
    # Genérico
    ("backup_2024-01-01.zip",                   "Generic"),
    ("documento_importante.pdf",                "Generic"),
    ("minha_colecao",                           "Generic"),
])
def test_detect_category(name, expected):
    assert detect_category(name) == expected


# ── record_upload ────────────────────────────────────────────────────────────

def test_record_upload_cria_registro(tmp_path):
    db_file = tmp_path / "history.db"
    with patch("upapasta.catalog._db_path", return_value=db_file):
        rowid = record_upload(
            nome_original="Dune.2021.mkv",
            senha_rar="abc123",
            tamanho_bytes=4_000_000_000,
            grupo_usenet="alt.binaries.movies",
            duracao_upload_s=120.5,
        )
    assert rowid == 1
    assert db_file.exists()


def test_record_upload_categoria_inferida(tmp_path):
    import sqlite3
    db_file = tmp_path / "history.db"
    with patch("upapasta.catalog._db_path", return_value=db_file):
        record_upload(nome_original="Breaking.Bad.S02E03.mkv")
    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT categoria FROM uploads").fetchone()
    conn.close()
    assert row[0] == "TV"


def test_record_upload_salva_nzb_blob(tmp_path):
    import sqlite3
    nzb = tmp_path / "test.nzb"
    nzb.write_bytes(b"<nzb>fake</nzb>")
    db_file = tmp_path / "history.db"
    with patch("upapasta.catalog._db_path", return_value=db_file):
        record_upload(nome_original="test.mkv", caminho_nzb=str(nzb))
    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT nzb_blob FROM uploads").fetchone()
    conn.close()
    assert row[0] == b"<nzb>fake</nzb>"


def test_record_upload_nzb_ausente_nao_falha(tmp_path):
    db_file = tmp_path / "history.db"
    with patch("upapasta.catalog._db_path", return_value=db_file):
        rowid = record_upload(
            nome_original="test.mkv",
            caminho_nzb="/caminho/inexistente.nzb",
        )
    assert rowid == 1


# ── run_post_upload_hook ─────────────────────────────────────────────────────

def test_hook_nao_executado_sem_configuracao():
    """Sem POST_UPLOAD_SCRIPT no env_vars, não deve fazer nada."""
    run_post_upload_hook({}, nome_original="test.mkv")  # não levanta


def test_hook_nao_executado_com_path_invalido(tmp_path, capsys):
    env = {"POST_UPLOAD_SCRIPT": str(tmp_path / "nao_existe.sh")}
    run_post_upload_hook(env, nome_original="test.mkv")
    captured = capsys.readouterr()
    assert "não encontrado" in captured.out


def test_hook_executado_com_envvars(tmp_path):
    script = tmp_path / "hook.sh"
    out_file = tmp_path / "result.txt"
    script.write_text(f'#!/bin/sh\necho "$UPAPASTA_NOME_ORIGINAL" > {out_file}\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    env = {"POST_UPLOAD_SCRIPT": str(script)}
    run_post_upload_hook(env, nome_original="Dune.2021.mkv", senha_rar="s3cr3t")

    assert out_file.read_text().strip() == "Dune.2021.mkv"


def test_hook_avisa_codigo_nao_zero(tmp_path, capsys):
    script = tmp_path / "fail.sh"
    script.write_text("#!/bin/sh\nexit 42\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    env = {"POST_UPLOAD_SCRIPT": str(script)}
    run_post_upload_hook(env, nome_original="test.mkv")

    captured = capsys.readouterr()
    assert "42" in captured.out
