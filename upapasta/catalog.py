"""
catalog.py

Catálogo local de uploads em SQLite (~/.config/upapasta/history.db).
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Detecção de categoria ────────────────────────────────────────────────────

# Padrões ordenados do mais específico para o mais genérico
_ANIME_RE = re.compile(
    r"""
    (?:
        \[[\w\-. ]+\]          # [SubGroup]
        | (?<![A-Z])           # evita falso positivo em siglas
    )
    .*?
    (?:
        \s-\s\d{1,3}           # " - 01"
        | EP\d{1,3}            # EP01
    )
    (?:\s|$|\[)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TV_RE = re.compile(
    r"""
    (?:
        [Ss]\d{1,2}[Ee]\d{1,2}   # S01E01, s1e2
        | \d{1,2}x\d{1,2}         # 1x01
        | Season[\s._-]?\d+        # Season 2
        | Complete[\s._-]Series    # Complete Series
        | MINISERIES               # MINISERIES
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_MOVIE_RE = re.compile(
    r"""
    (?:^|[\s._])               # início ou separador de título (não hífen)
    (?:19|20)\d{2}             # ano entre 1900-2099
    (?!-\d{2}-)                # não seguido de -MM- (padrão de data ISO)
    (?:$|[\s._-])
    """,
    re.VERBOSE,
)


def detect_category(name: str) -> str:
    """Detecta categoria a partir do nome do arquivo ou pasta.

    Retorna: "Anime", "TV", "Movie" ou "Generic".
    """
    stem = Path(name).stem
    if _ANIME_RE.search(stem):
        return "Anime"
    if _TV_RE.search(stem):
        return "TV"
    if _MOVIE_RE.search(stem):
        return "Movie"
    return "Generic"


# ── Banco de dados ───────────────────────────────────────────────────────────

def _db_path() -> Path:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "upapasta"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg / "history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS uploads (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            data_upload      TEXT NOT NULL,           -- ISO-8601 UTC
            nome_original    TEXT NOT NULL,
            nome_ofuscado    TEXT,
            senha_rar        TEXT,
            tamanho_bytes    INTEGER,
            categoria        TEXT,
            tmdb_id          TEXT,
            grupo_usenet     TEXT,
            servidor_nntp    TEXT,
            redundancia_par2 TEXT,
            duracao_upload_s REAL,
            num_arquivos_rar INTEGER,
            caminho_nzb      TEXT,
            nzb_blob         BLOB,
            subject          TEXT
        );
    """)
    conn.commit()


def record_upload(
    *,
    nome_original: str,
    nome_ofuscado: Optional[str] = None,
    senha_rar: Optional[str] = None,
    tamanho_bytes: Optional[int] = None,
    tmdb_id: Optional[str] = None,
    grupo_usenet: Optional[str] = None,
    servidor_nntp: Optional[str] = None,
    redundancia_par2: Optional[str] = None,
    duracao_upload_s: Optional[float] = None,
    num_arquivos_rar: Optional[int] = None,
    caminho_nzb: Optional[str] = None,
    subject: Optional[str] = None,
) -> int:
    """Registra um upload bem-sucedido. Retorna o id inserido."""
    categoria = detect_category(nome_original)

    nzb_blob: Optional[bytes] = None
    if caminho_nzb and os.path.exists(caminho_nzb):
        try:
            with open(caminho_nzb, "rb") as f:
                nzb_blob = f.read()
        except OSError:
            pass

    data_upload = datetime.now(timezone.utc).isoformat()

    conn = _connect()
    _migrate(conn)
    cur = conn.execute(
        """
        INSERT INTO uploads (
            data_upload, nome_original, nome_ofuscado, senha_rar,
            tamanho_bytes, categoria, tmdb_id, grupo_usenet,
            servidor_nntp, redundancia_par2, duracao_upload_s,
            num_arquivos_rar, caminho_nzb, nzb_blob, subject
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data_upload, nome_original, nome_ofuscado, senha_rar,
            tamanho_bytes, categoria, tmdb_id, grupo_usenet,
            servidor_nntp, redundancia_par2, duracao_upload_s,
            num_arquivos_rar, caminho_nzb, nzb_blob, subject,
        ),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


# ── Hook pós-upload ──────────────────────────────────────────────────────────

def run_post_upload_hook(
    env_vars: dict,
    *,
    nzb_path: Optional[str] = None,
    nfo_path: Optional[str] = None,
    senha_rar: Optional[str] = None,
    nome_original: str,
    nome_ofuscado: Optional[str] = None,
    tamanho_bytes: Optional[int] = None,
    grupo_usenet: Optional[str] = None,
) -> None:
    """Executa POST_UPLOAD_SCRIPT do .env, se configurado.

    O script recebe as informações do upload via variáveis de ambiente
    prefixadas com UPAPASTA_, sem argumentos posicionais — assim scripts
    existentes não quebram quando novos campos forem adicionados.
    """
    script = env_vars.get("POST_UPLOAD_SCRIPT") or os.environ.get("POST_UPLOAD_SCRIPT")
    if not script:
        return

    script = os.path.expanduser(script)
    if not os.path.isfile(script):
        print(f"⚠️  POST_UPLOAD_SCRIPT não encontrado: {script}")
        return

    hook_env = os.environ.copy()
    hook_env.update({
        "UPAPASTA_NZB":            nzb_path or "",
        "UPAPASTA_NFO":            nfo_path or "",
        "UPAPASTA_SENHA":          senha_rar or "",
        "UPAPASTA_NOME_ORIGINAL":  nome_original,
        "UPAPASTA_NOME_OFUSCADO":  nome_ofuscado or "",
        "UPAPASTA_TAMANHO":        str(tamanho_bytes or ""),
        "UPAPASTA_GRUPO":          grupo_usenet or "",
    })

    try:
        result = subprocess.run(
            [script],
            env=hook_env,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            print(f"⚠️  POST_UPLOAD_SCRIPT saiu com código {result.returncode}")
    except subprocess.TimeoutExpired:
        print("⚠️  POST_UPLOAD_SCRIPT ultrapassou o timeout de 60s")
    except OSError as e:
        print(f"⚠️  Falha ao executar POST_UPLOAD_SCRIPT: {e}")
