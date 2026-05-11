#!/usr/bin/env python3
"""
make7z.py

Recebe um caminho para uma pasta e cria um arquivo .7z com o mesmo nome
na pasta pai. Requer o utilitário de linha de comando `7z` (instale via
`sudo apt install p7zip-full` em Debian/Ubuntu ou p7zip em macOS).

Uso:
  python3 make7z.py /caminho/para/minha_pasta

Opções:
  -f, --force    Sobrescrever arquivo .7z existente

Saídas:
  Código 0  -> sucesso
  Código 2  -> pasta de entrada inexistente / não é diretório
  Código 3  -> arquivo .7z já existe (use --force para sobrescrever)
  Código 4  -> utilitário `7z` não encontrado
  Código 5  -> erro ao executar o comando 7z
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


def find_7z() -> str | None:
    """Procura o executável '7z' no PATH ou pasta bin local."""
    for cmd in ("7z", "7z.exe", "7za", "7za.exe"):
        path = get_tool_path(cmd)
        if path:
            return path
    return None


_MIN_SPLIT_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB — abaixo disso, 7z único
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
    """Calcula o tamanho ideal de cada volume 7z em bytes."""
    if total_bytes < _MIN_SPLIT_SIZE:
        return None

    raw = math.ceil(total_bytes / _MAX_VOLUMES)
    vol = max(_MIN_VOLUME_SIZE, raw)

    five_mb = 5 * 1024 * 1024
    vol = math.ceil(vol / five_mb) * five_mb
    return vol


def make_7z(
    input_path: str,
    force: bool = False,
    threads: Optional[int] = None,
    password: Optional[str] = None,
    bar: Optional[PhaseBar] = None,
) -> Tuple[int, Optional[str]]:
    """Cria um arquivo 7z para a pasta ou arquivo fornecido."""
    input_path = os.path.abspath(input_path)
    is_file = os.path.isfile(input_path)
    is_dir = os.path.isdir(input_path)

    if not is_file and not is_dir:
        print(_("Erro: '{path}' não existe ou não é um arquivo/diretório.").format(path=input_path))
        return 2, None

    parent = os.path.dirname(input_path)

    if is_dir:
        base = os.path.basename(os.path.normpath(input_path))
        archive_target = base
    else:
        base = os.path.splitext(os.path.basename(input_path))[0]
        archive_target = os.path.basename(input_path)

    out_7z = os.path.join(parent, base + ".7z")
    # 7z volumes são .7z.001, .7z.002...
    existing_parts = glob.glob(os.path.join(parent, glob.escape(base) + ".7z.[0-9][0-9][0-9]"))

    if (os.path.exists(out_7z) or existing_parts) and not force:
        print(
            _(
                "Erro: '{archive}' ou volumes parciais já existem. Use --force para sobrescrever."
            ).format(archive=out_7z)
        )
        return 3, None

    if force:
        if os.path.exists(out_7z):
            try:
                os.remove(out_7z)
            except OSError:
                pass
        for part in existing_parts:
            try:
                os.remove(part)
            except OSError:
                pass

    exe_7z = find_7z()
    if not exe_7z:
        print(_("Erro: utilitário '7z' não encontrado. Instale p7zip-full."))
        return 4, None

    num_threads = min(threads if threads is not None else (os.cpu_count() or 4), 64)

    # a: add, -mx0: store, -mmt: multithreading, -y: yes to all
    cmd = [exe_7z, "a", "-mx0", f"-mmt{num_threads}", "-y"]
    if password:
        # -p{pass} -mhe=on (on for .7z format only, encrypts filenames)
        cmd.append(f"-p{password}")
        cmd.append("-mhe=on")

    if is_dir:
        total_bytes = _folder_size(input_path)
        vol_bytes = _volume_size_bytes(total_bytes)
        if vol_bytes is not None:
            cmd.append(f"-v{vol_bytes}b")
            num_vols = max(1, -(-total_bytes // vol_bytes))
            msg = _(
                "Criando '{archive}' em volumes de {size} MB (~{count} partes, {total} MB total)..."
            ).format(
                archive=out_7z,
                size=vol_bytes // (1024 * 1024),
                count=num_vols,
                total=total_bytes // (1024 * 1024),
            )
            if bar:
                bar.log(msg)
            else:
                print(msg)
        else:
            msg = _(
                "Criando '{archive}' a partir de '{input}' (usando {threads} threads)..."
            ).format(archive=out_7z, input=input_path, threads=num_threads)
            if bar:
                bar.log(msg)
            else:
                print(msg)
    else:
        # Arquivo único
        vol_bytes = None
        msg = _("Criando '{archive}' a partir de '{target}' (usando {threads} threads)...").format(
            archive=out_7z, target=archive_target, threads=num_threads
        )
        if bar:
            bar.log(msg)
        else:
            print(msg)

    cmd += [out_7z, archive_target]

    try:
        captured_output: list[str] = []
        with managed_popen(
            cmd,
            cwd=parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        ) as proc:
            output_queue: Queue[str | None] = Queue()
            reader_thread = threading.Thread(
                target=_read_output,
                args=(proc.stdout, output_queue),
                daemon=True,
            )
            reader_thread.start()

            # Processa progresso (7z emite 0%... 50%... 100%)
            _process_output(output_queue, bar=bar, captured_lines=captured_output)
            rc = proc.wait()

        if rc == 0:
            if not bar:
                print(_("Arquivo .7z criado com sucesso."))
            if vol_bytes is None:
                return 0, out_7z
            matches = glob.glob(os.path.join(parent, glob.escape(base) + ".7z.001"))
            if matches:
                return 0, matches[0]
            return 0, out_7z
        else:
            error_context = "\n".join(captured_output[-10:])
            if error_context.strip():
                print(_("\n--- Log de erro do 7z ---"))
                for _l in error_context.splitlines():
                    if _l.strip():
                        print(f"  {_l}")
                print("--------------------------\n")
            if not bar:
                print(_("Erro: '7z' retornou código {rc}.").format(rc=rc))
            return 5, None
    except KeyboardInterrupt:
        raise
    except FileNotFoundError:
        print(_("Erro: binário '7z' não encontrado no PATH."))
        return 4, None
    except Exception as e:
        print(_("Erro ao executar '7z': {error}").format(error=e))
        return 5, None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=_("Cria um .7z de uma pasta com o mesmo nome"))
    p.add_argument("folder", help=_("Caminho para a pasta a ser compactada"))
    p.add_argument("-f", "--force", action="store_true", help=_("Sobrescrever .7z existente"))
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    res, archive_path = make_7z(args.folder, force=args.force)
    exit(res)
