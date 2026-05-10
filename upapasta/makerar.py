#!/usr/bin/env python3
"""
makerar.py

Recebe um caminho para uma pasta e cria um arquivo .rar com o mesmo nome
na pasta pai. Requer o utilitário de linha de comando `rar` (instale via
`sudo apt install rar` em Debian/Ubuntu ou baixe de RARLAB).

Uso:
  python3 makerar.py /caminho/para/minha_pasta

Opções:
  -f, --force    Sobrescrever arquivo .rar existente

Saídas:
  Código 0  -> sucesso
  Código 2  -> pasta de entrada inexistente / não é diretório
  Código 3  -> arquivo .rar já existe (use --force para sobrescrever)
  Código 4  -> utilitário `rar` não encontrado
  Código 5  -> erro ao executar o comando rar
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import subprocess
import threading
from queue import Queue
from typing import TYPE_CHECKING, Optional, Tuple

from ._process import managed_popen
from ._progress import _process_output, _read_output
from .i18n import _
from .tools import get_tool_path

if TYPE_CHECKING:
    from .ui import PhaseBar


def find_rar() -> str | None:
    """Procura o executável 'rar' no PATH ou pasta bin local."""
    for cmd in ("rar", "rar.exe"):
        path = get_tool_path(cmd)
        if path:
            return path
    return None


_MIN_SPLIT_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB — abaixo disso, RAR único
_MIN_VOLUME_SIZE = 1024 * 1024 * 1024  # 1 GB — tamanho mínimo de cada parte
_MAX_VOLUMES = 100


def _folder_size(path: str) -> int:
    """Retorna o tamanho total em bytes de todos os arquivos sob path."""
    total = 0
    for dirpath, _d, filenames in os.walk(path):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                pass
    return total


def _volume_size_bytes(total_bytes: int) -> Optional[int]:
    """
    Calcula o tamanho ideal de cada volume RAR em bytes.
    Retorna None quando o conteúdo é pequeno o suficiente para um RAR único.

    Regras:
      - Abaixo de _MIN_SPLIT_SIZE → sem volumes (None)
      - Tamanho = max(_MIN_VOLUME_SIZE, ceil(total / _MAX_VOLUMES))
      - Arredondado para o próximo múltiplo de 5 MB para ficar redondo
    """
    if total_bytes < _MIN_SPLIT_SIZE:
        return None

    raw = math.ceil(total_bytes / _MAX_VOLUMES)
    vol = max(_MIN_VOLUME_SIZE, raw)

    five_mb = 5 * 1024 * 1024
    vol = math.ceil(vol / five_mb) * five_mb
    return vol


def make_rar(
    input_path: str,
    force: bool = False,
    threads: Optional[int] = None,
    password: Optional[str] = None,
    bar: Optional[PhaseBar] = None,
) -> Tuple[int, Optional[str]]:
    """Cria um arquivo RAR para a pasta ou arquivo fornecido.

    Aceita tanto diretórios quanto arquivos únicos.
    Para diretórios: inclui conteúdo recursivamente, divide em volumes se > 10 GB.
    Para arquivos: cria RAR sem volume splitting (útil para obfuscação ou senha).

    Retorna (código_de_retorno, primeiro_arquivo_gerado).
    Sem volumes: ("nome.rar",). Com volumes: primeiro é "nome.part001.rar".
    Em caso de erro o segundo elemento é sempre None.
    """
    input_path = os.path.abspath(input_path)
    is_file = os.path.isfile(input_path)
    is_dir = os.path.isdir(input_path)

    if not is_file and not is_dir:
        print(_("Erro: '{path}' não existe ou não é um arquivo/diretório.").format(path=input_path))
        return 2, None

    parent = os.path.dirname(input_path)

    if is_dir:
        base = os.path.basename(os.path.normpath(input_path))
        archive_target = base  # argumento para o rar (relativo ao cwd=parent)
    else:
        # Arquivo único: usa o stem (sem extensão) como nome do RAR
        base = os.path.splitext(os.path.basename(input_path))[0]
        archive_target = os.path.basename(input_path)

    out_rar = os.path.join(parent, base + ".rar")
    existing_parts = glob.glob(os.path.join(parent, glob.escape(base) + ".part*.rar"))
    if (os.path.exists(out_rar) or existing_parts) and not force:
        print(
            _(
                "Erro: '{rar}' ou volumes parciais já existem. Use --force para sobrescrever."
            ).format(rar=out_rar)
        )
        return 3, None
    if force:
        if os.path.exists(out_rar):
            try:
                os.remove(out_rar)
            except OSError:
                pass
        for part in existing_parts:
            try:
                os.remove(part)
            except OSError:
                pass

    rar_exec = find_rar()
    if not rar_exec:
        print(_("Erro: utilitário 'rar' não encontrado. Instale-o (ex: sudo apt install rar)"))
        return 4, None

    num_threads = min(threads if threads is not None else (os.cpu_count() or 4), 64)

    # -m0 → store (sem compressão, mais rápido e vídeos já são comprimidos)
    # -ma5 → RAR5, -mt → threads
    # -hp cifra conteúdo E nomes de arquivo internos (mais forte que -p)
    if is_dir:
        total_bytes = _folder_size(input_path)
        vol_bytes = _volume_size_bytes(total_bytes)
        cmd = [rar_exec, "a", "-r", "-m0", f"-mt{num_threads}", "-ma5"]
        if password:
            cmd.append(f"-hp{password}")
        if force:
            cmd.append("-o+")
        if vol_bytes is not None:
            cmd.append(f"-v{vol_bytes}b")
            num_vols = max(1, -(-total_bytes // vol_bytes))  # ceil division
            msg = _(
                "Criando '{rar}' em volumes de {size} MB (~{count} partes, {total} MB total)..."
            ).format(
                rar=out_rar,
                size=vol_bytes // (1024 * 1024),
                count=num_vols,
                total=total_bytes // (1024 * 1024),
            )
            if bar:
                bar.log(msg)
            else:
                print(msg)
        else:
            msg = _("Criando '{rar}' a partir de '{input}' (usando {threads} threads)...").format(
                rar=out_rar, input=input_path, threads=num_threads
            )
            if bar:
                bar.log(msg)
            else:
                print(msg)
    else:
        # Arquivo único: sem volume splitting, sem flag -r
        total_bytes = os.path.getsize(input_path)
        vol_bytes = None
        cmd = [rar_exec, "a", "-m0", f"-mt{num_threads}", "-ma5"]
        if password:
            cmd.append(f"-hp{password}")
        if force:
            cmd.append("-o+")
        msg = _("Criando '{rar}' a partir de '{target}' (usando {threads} threads)...").format(
            rar=out_rar, target=archive_target, threads=num_threads
        )
        if bar:
            bar.log(msg)
        else:
            print(msg)

    cmd += [out_rar, archive_target]

    try:
        # Executa o rar e captura stdout/stderr para parsear progresso.
        # managed_popen garante SIGTERM → SIGKILL no filho se o Python receber
        # KeyboardInterrupt (Ctrl+C) ou qualquer outra exceção.
        with managed_popen(
            cmd,
            cwd=parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        ) as proc:
            # Fila para comunicação entre threads
            output_queue: Queue[str | None] = Queue()

            # Thread daemon: morrerá automaticamente quando o processo filho morrer
            reader_thread = threading.Thread(
                target=_read_output,
                args=(proc.stdout, output_queue),
                daemon=True,
            )
            reader_thread.start()

            # Processa output na thread principal
            last_percent, teve_percentual = _process_output(output_queue, bar=bar)

            # Aguarda o fim do processo
            rc = proc.wait()

        if rc == 0:
            if not bar:
                print(_("Arquivo .rar criado com sucesso."))
            if vol_bytes is None:
                return 0, out_rar
            matches = glob.glob(os.path.join(parent, glob.escape(base) + ".part*.rar"))
            if matches:
                return 0, sorted(matches)[0]
            # Volumes esperados mas não encontrados — rar gerou arquivo único
            if not bar:
                print(_("Aviso: volumes RAR não encontrados, usando arquivo único."))
            return 0, out_rar
        else:
            if not bar:
                print(_("Erro: 'rar' retornou código {rc}.").format(rc=rc))
            return 5, None
    except KeyboardInterrupt:
        # managed_popen ya terminó al hijo; se propaga al orquestador
        raise
    except FileNotFoundError:
        print(_("Erro: binário 'rar' não encontrado no PATH."))
        return 4, None
    except PermissionError as e:
        print(_("Erro de permissão ao executar 'rar': {error}").format(error=e))
        return 5, None
    except OSError as e:
        print(_("Erro de I/O ao executar 'rar': {error}").format(error=e))
        return 5, None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=_("Cria um .rar de uma pasta com o mesmo nome"))
    p.add_argument("folder", help=_("Caminho para a pasta a ser compactada"))
    p.add_argument("-f", "--force", action="store_true", help=_("Sobrescrever .rar existente"))
    return p.parse_args()
