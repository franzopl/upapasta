"""
tui/external_nzb.py

Mecanismo para escanear diretórios em busca de arquivos .nzb externos
e mapear quais arquivos locais possuem backup.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# A senha de um NZB fica em <meta type="password"> dentro de <head>, sempre
# antes do primeiro <file>. Lemos só esse prefixo — nunca o arquivo inteiro,
# que pode ter dezenas de MB.
_HEAD_READ_CAP = 65536
_PASSWORD_META = re.compile(
    rb"<meta[^>]*\btype=[\"']password[\"'][^>]*>([^<]*)</meta>", re.IGNORECASE
)


@dataclass(frozen=True)
class ExternalNzbInfo:
    """Dados de um .nzb externo encontrado no scan."""

    path: Path
    has_password: bool = False


def nzb_has_password(nzb_path: Path) -> bool:
    """
    Detecta se um .nzb tem senha lendo apenas o <head> (até o primeiro <file>).
    Retorna False em qualquer erro de leitura.
    """
    try:
        head = b""
        with open(nzb_path, "rb") as fh:
            while len(head) < _HEAD_READ_CAP:
                chunk = fh.read(8192)
                if not chunk:
                    break
                head += chunk
                idx = head.find(b"<file")
                if idx != -1:
                    head = head[:idx]
                    break
    except OSError:
        return False
    match = _PASSWORD_META.search(head)
    return bool(match and match.group(1).strip())


class ExternalNzbIndex:
    """
    Índice de arquivos .nzb encontrados em diretórios externos.
    Mapeia os nomes dos arquivos (stem) para o respectivo ExternalNzbInfo.
    """

    def __init__(self, search_paths: list[Path]) -> None:
        self.search_paths = search_paths
        self._known: dict[str, ExternalNzbInfo] = {}
        # Cache de senha por path: evita reler .nzb inalterado em cada scan.
        self._pw_cache: dict[Path, tuple[tuple[float, int], bool]] = {}

    def scan(self) -> None:
        """Varre os diretórios configurados em busca de .nzb."""
        found: dict[str, ExternalNzbInfo] = {}
        fresh_cache: dict[Path, tuple[tuple[float, int], bool]] = {}
        for path in self.search_paths:
            if not path.exists() or not path.is_dir():
                continue
            try:
                for root, _dirs, files in os.walk(path):
                    for file in files:
                        if not file.lower().endswith(".nzb"):
                            continue
                        # "Filme.mkv.nzb" -> stem "Filme.mkv"; "Filme.nzb" -> "Filme"
                        full = Path(root) / file
                        try:
                            st = full.stat()
                        except OSError:
                            continue
                        sig = (st.st_mtime, st.st_size)
                        cached = self._pw_cache.get(full)
                        if cached is not None and cached[0] == sig:
                            has_pw = cached[1]
                        else:
                            has_pw = nzb_has_password(full)
                        fresh_cache[full] = (sig, has_pw)
                        found[Path(file).stem.lower()] = ExternalNzbInfo(
                            path=full, has_password=has_pw
                        )
            except Exception:
                # Ignora erros de permissão etc durante o scan
                pass
        self._known = found
        self._pw_cache = fresh_cache

    def lookup(self, filename: str) -> Optional[ExternalNzbInfo]:
        """Retorna o ExternalNzbInfo correspondente a um nome, ou None."""
        info = self._known.get(filename.lower())
        if info is not None:
            return info
        # Se for um arquivo com extensão, tenta o stem
        return self._known.get(Path(filename).stem.lower())

    def is_present(self, filename: str) -> bool:
        """Verifica se um arquivo/pasta (pelo nome) possui um NZB externo."""
        return self.lookup(filename) is not None
