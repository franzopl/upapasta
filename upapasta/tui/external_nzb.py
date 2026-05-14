"""
tui/external_nzb.py

Mecanismo para escanear diretórios em busca de arquivos .nzb externos
e mapear quais arquivos locais possuem backup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set


class ExternalNzbIndex:
    """
    Índice de arquivos .nzb encontrados em diretórios externos.
    Mapeia os nomes dos arquivos (stem) para identificação rápida.
    """

    def __init__(self, search_paths: list[Path]) -> None:
        self.search_paths = search_paths
        self._known_stems: Set[str] = set()

    def scan(self) -> None:
        """Varre os diretórios configurados em busca de .nzb."""
        new_stems: Set[str] = set()
        for path in self.search_paths:
            if not path.exists() or not path.is_dir():
                continue

            try:
                # Busca recursiva por .nzb
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(".nzb"):
                            # Adicionamos o nome base sem .nzb
                            # Ex: "Filme.mkv.nzb" -> stem é "Filme.mkv"
                            # Ex: "Filme.nzb" -> stem é "Filme"
                            p = Path(file)
                            new_stems.add(p.stem.lower())
            except Exception:
                # Ignora erros de permissão etc durante o scan
                pass

        self._known_stems = new_stems

    def is_present(self, filename: str) -> bool:
        """
        Verifica se um arquivo ou pasta (pelo nome) possui um NZB externo correspondente.
        Tenta match exato ou match por stem.
        """
        name_lower = filename.lower()
        if name_lower in self._known_stems:
            return True

        # Se for um arquivo com extensão, tenta o stem
        stem = Path(filename).stem.lower()
        if stem in self._known_stems:
            return True

        return False
