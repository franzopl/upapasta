"""
catalog.py

Catálogo local de uploads em JSONL (~/.config/upapasta/history.jsonl).
Cada linha é um objeto JSON independente — append-only, sem dependências externas.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Detecção de categoria ────────────────────────────────────────────────────

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
    stem = Path(name).stem
    if _ANIME_RE.search(stem):
        return "Anime"
    if _TV_RE.search(stem):
        return "TV"
    if _MOVIE_RE.search(stem):
        return "Movie"
    return "Generic"


# ── Arquivo de histórico ─────────────────────────────────────────────────────

def _cfg_dir() -> Path:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "upapasta"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


def _history_path() -> Path:
    return _cfg_dir() / "history.jsonl"


def _archive_nzb(src: str, stamp: str, nome: str) -> Optional[str]:
    nzb_dir = _cfg_dir() / "nzb"
    nzb_dir.mkdir(exist_ok=True)
    safe_nome = re.sub(r"[^\w\-. ]", "_", nome)[:80]
    dest = nzb_dir / f"{stamp}_{safe_nome}.nzb"
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
    return str(dest)


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
) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    nzb_arquivado: Optional[str] = None
    if caminho_nzb and os.path.exists(caminho_nzb):
        try:
            nzb_arquivado = _archive_nzb(caminho_nzb, stamp, nome_original)
        except OSError:
            pass

    record = {
        "data_upload":      datetime.now(timezone.utc).isoformat(),
        "nome_original":    nome_original,
        "categoria":        detect_category(nome_original),
        "nome_ofuscado":    nome_ofuscado,
        "senha_rar":        senha_rar,
        "tamanho_bytes":    tamanho_bytes,
        "tmdb_id":          tmdb_id,
        "grupo_usenet":     grupo_usenet,
        "servidor_nntp":    servidor_nntp,
        "redundancia_par2": redundancia_par2,
        "duracao_upload_s": duracao_upload_s,
        "num_arquivos_rar": num_arquivos_rar,
        "caminho_nzb":      nzb_arquivado,
        "subject":          subject,
    }

    with open(_history_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
    """Executa POST_UPLOAD_SCRIPT do .env, se configurado."""
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
