#!/usr/bin/env python3
"""
makepar.py

Cria arquivos de paridade (.par2) para um arquivo/pasta fornecido.

Uso:
  python3 makepar.py arquivo.rar

Opções:
  -r, --redundancy PERCENT   Percentual de redundância (padrão: 10%). Fixo para Usenet.
  -f, --force                Sobrescrever arquivos .par2 existentes
  --profile PROFILE          Perfil de otimização: fast, balanced (padrão), safe

Perfis:
  fast                       Máxima velocidade: redundância 5%
  balanced                   Equilibrado (PADRÃO): redundância 10%, slice dinâmico automático
  safe                       Alta proteção: redundância 20%

Slice size (parpar):
  Calculado automaticamente a partir de ARTICLE_SIZE no ~/.config/upapasta/.env.
  Fórmula base: ARTICLE_SIZE * 2. Escalonado conforme o tamanho total do set.
  O flag -S (auto-scaling) é sempre ativado para garantir blocos PAR2 adequados.

Retornos:
  0: sucesso
  2: arquivo de entrada inválido
  3: arquivo .par2 já existe (use --force)
  4: utilitário 'parpar' ou 'par2' não encontrado
  5: erro ao executar o utilitário
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import re
import shutil
import string
import subprocess
import sys
import threading
from queue import Queue
from typing import TYPE_CHECKING, Optional, Tuple

from ._process import managed_popen
from ._progress import _process_output, _read_output
from .i18n import _
from .par_utils import (
    compute_dynamic_slice,
    fmt_size,
    get_article_size_bytes,
    get_parpar_memory_limit,
    parse_size,
)
from .profiles import DEFAULT_PROFILE, PROFILES
from .tools import get_tool_path

if TYPE_CHECKING:
    from .ui import PhaseBar

# ── Memória disponível ────────────────────────────────────────────────────────


# ── Obfuscação ────────────────────────────────────────────────────────────────


def generate_random_name(min_len: int = 10, max_len: int = 30) -> str:
    """Gera um nome de arquivo aleatório com letras e dígitos e comprimento variável."""
    length = random.randint(min_len, max_len)
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _i in range(length))


def link_tree(src: str, dst: str) -> None:
    """Cria uma árvore de hardlinks espelhando a estrutura de src em dst."""
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dest_root = os.path.join(dst, rel_path)
        for d in dirs:
            os.makedirs(os.path.join(dest_root, d), exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(dest_root, f)
            try:
                os.link(src_file, dst_file)
            except OSError as e:
                # Se falhar hardlink (ex: cross-device), deixa subir para o fallback no obfuscate_and_par
                raise e


def _deep_obfuscate_tree(path: str) -> dict[str, str]:
    """
    Percorre a árvore recursivamente e renomeia tudo.
    Retorna mapeamento {novo_caminho_relativo: caminho_original_relativo}.
    """
    mapping = {}

    # Vamos usar um dicionário que mapeia o caminho RELATIVO ATUAL para o RELATIVO ORIGINAL.
    # Inicialmente, a árvore está original.
    current_to_original = {".": "."}

    for root, dirs, files in os.walk(path, topdown=True):
        rel_root = os.path.relpath(root, path)
        orig_rel_root = current_to_original[rel_root]

        # 1. Renomeia arquivos
        for f in files:
            name, ext = os.path.splitext(f)
            new_name = generate_random_name() + ext

            os.replace(os.path.join(root, f), os.path.join(root, new_name))

            new_rel_f = os.path.normpath(os.path.join(rel_root, new_name))
            orig_rel_f = os.path.normpath(os.path.join(orig_rel_root, f))
            mapping[new_rel_f] = orig_rel_f

        # 2. Renomeia diretórios
        for i, d in enumerate(dirs):
            new_name = generate_random_name()

            os.replace(os.path.join(root, d), os.path.join(root, new_name))

            new_rel_d = os.path.normpath(os.path.join(rel_root, new_name))
            orig_rel_d = os.path.normpath(os.path.join(orig_rel_root, d))

            # Atualiza dirs para os.walk continuar
            dirs[i] = new_name

            # Registra mapeamentos
            current_to_original[new_rel_d] = orig_rel_d
            mapping[new_rel_d] = orig_rel_d

    return mapping


def _revert_obfuscation(
    is_folder: bool,
    is_rar_vol_set: bool,
    obfuscated_path: str,
    input_path: str,
    parent_dir: str,
    random_base: str,
    obfuscated_map: dict[str, str],
    was_linked: bool = False,
) -> None:
    """
    Reverte a ofuscação (renomeação ou hardlink) dos arquivos do usuário.

    Chamada em qualquer saída anormal de obfuscate_and_par — erro de paridade,
    exceção Python, ou KeyboardInterrupt.
    """
    if was_linked:
        print(_("  Removendo hardlinks temporários de ofuscação..."))
        try:
            if is_folder:
                shutil.rmtree(obfuscated_path)
            elif is_rar_vol_set:
                # Remove volumes ofuscados
                vols = glob.glob(os.path.join(parent_dir, glob.escape(random_base) + ".part*.rar"))
                for v in vols:
                    os.remove(v)
            else:
                os.remove(obfuscated_path)
            print(_("  ✓ Hardlinks removidos."))
        except OSError as e:
            print(_("  ✗ Falha ao remover hardlinks: {error}").format(error=e))
        return

    print(_("  Revertendo ofuscação para restaurar nomes originais..."))
    if is_folder:
        try:
            os.replace(obfuscated_path, input_path)
            print(_("  ✓ Pasta restaurada: {name}").format(name=os.path.basename(input_path)))
        except OSError as e:
            print(
                _("  ✗ Falha ao reverter pasta '{obfuscated}' → '{input}': {error}").format(
                    obfuscated=obfuscated_path, input=input_path, error=e
                )
            )
            print(
                _("    AÇÃO MANUAL: renomeie '{obfuscated}' de volta para '{input}'").format(
                    obfuscated=obfuscated_path, input=input_path
                )
            )

    elif is_rar_vol_set and obfuscated_map:
        orig_base = list(obfuscated_map.values())[0]
        vols = sorted(glob.glob(os.path.join(parent_dir, glob.escape(random_base) + ".part*.rar")))
        ok = 0
        for vol in vols:
            suffix = os.path.basename(vol)[len(random_base) :]
            original = os.path.join(parent_dir, orig_base + suffix)
            try:
                os.replace(vol, original)
                ok += 1
            except OSError as e:
                print(
                    _("  ✗ Falha ao reverter '{vol}' → '{original}': {error}").format(
                        vol=os.path.basename(vol), original=orig_base + suffix, error=e
                    )
                )
                print(_("    AÇÃO MANUAL: renomeie o arquivo manualmente."))
        if ok:
            print(
                _("  ✓ {count} volume(s) RAR restaurado(s): {base}.part*.rar").format(
                    count=ok, base=orig_base
                )
            )

    else:
        try:
            os.replace(obfuscated_path, input_path)
            print(_("  ✓ Arquivo restaurado: {name}").format(name=os.path.basename(input_path)))
        except OSError as e:
            print(
                _("  ✗ Falha ao reverter '{obfuscated}' → '{input}': {error}").format(
                    obfuscated=obfuscated_path, input=input_path, error=e
                )
            )
            print(
                _("    AÇÃO MANUAL: renomeie '{obfuscated}' de volta para '{input}'").format(
                    obfuscated=os.path.basename(obfuscated_path), input=os.path.basename(input_path)
                )
            )


def _obfuscate_folder(
    input_path: str, parent_dir: str, base: str, random_base: str
) -> Tuple[str, dict[str, str], bool, str]:
    """Cria visão ofuscada de uma pasta via hardlinks (ou rename fallback)."""
    obfuscated_path = os.path.join(parent_dir, random_base)
    print(_("Ofuscando pasta (hardlink): {base} → {random}").format(base=base, random=random_base))
    try:
        link_tree(input_path, obfuscated_path)
        was_linked = True
    except OSError:
        print(
            _("  ⚠️ Hardlink falhou (possível cross-device). Usando rename (seeding pode quebrar).")
        )
        # Se o link_tree criou o diretório de destino antes de falhar,
        # precisamos removê-lo para que o os.replace funcione no Windows.
        if os.path.exists(obfuscated_path):
            try:
                if os.path.isdir(obfuscated_path):
                    shutil.rmtree(obfuscated_path, ignore_errors=True)
                else:
                    os.remove(obfuscated_path)
            except OSError:
                pass

        if sys.platform == "win32":
            import time

            # No Windows, os.replace não funciona se o destino for um diretório existente.
            # E shutil.rmtree pode levar um tempo para liberar o nome no sistema de arquivos.
            for i in range(5):
                try:
                    if os.path.exists(obfuscated_path):
                        if os.path.isdir(obfuscated_path):
                            shutil.rmtree(obfuscated_path, ignore_errors=True)
                        else:
                            os.remove(obfuscated_path)
                    os.rename(input_path, obfuscated_path)
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                # Última tentativa desesperada
                os.replace(input_path, obfuscated_path)
        else:
            os.replace(input_path, obfuscated_path)

        was_linked = False
    par_input = input_path if was_linked else obfuscated_path
    return obfuscated_path, {random_base: base}, was_linked, par_input


def _obfuscate_rar_vol_set(
    input_path: str, parent_dir: str, name_no_ext: str, random_base: str
) -> Tuple[str, dict[str, str], bool, str]:
    """Cria visão ofuscada de um conjunto de volumes RAR."""
    original_base = name_no_ext.rsplit(".part", 1)[0]
    volumes = sorted(
        glob.glob(os.path.join(parent_dir, glob.escape(original_base) + ".part*.rar"))
    ) or [input_path]
    print(
        _("Ofuscando volumes RAR (hardlink): {orig}.part*.rar → {random}.part*.rar").format(
            orig=original_base, random=random_base
        )
    )
    try:
        for vol in volumes:
            suffix = os.path.basename(vol)[len(original_base) :]
            os.link(vol, os.path.join(parent_dir, random_base + suffix))
        was_linked = True
    except OSError:
        print(_("  ⚠️ Hardlink falhou. Usando rename."))
        for v in glob.glob(os.path.join(parent_dir, random_base + ".part*.rar")):
            try:
                os.remove(v)
            except OSError:
                pass
        for vol in volumes:
            suffix = os.path.basename(vol)[len(original_base) :]
            os.replace(vol, os.path.join(parent_dir, random_base + suffix))
        was_linked = False
    first_suffix = os.path.basename(volumes[0])[len(original_base) :]
    obfuscated_path = os.path.join(parent_dir, random_base + first_suffix)
    par_input = (
        os.path.join(parent_dir, original_base + first_suffix) if was_linked else obfuscated_path
    )
    return obfuscated_path, {random_base: original_base}, was_linked, par_input


def _obfuscate_single_file(
    input_path: str, parent_dir: str, base: str, random_base: str
) -> Tuple[str, dict[str, str], bool, str]:
    """Cria visão ofuscada de um arquivo único."""
    name_no_ext, ext = os.path.splitext(base)
    obfuscated_path = os.path.join(parent_dir, random_base + ext)
    print(
        _("Ofuscando (hardlink): {base} → {obfuscated}").format(
            base=base, obfuscated=os.path.basename(obfuscated_path)
        )
    )
    try:
        os.link(input_path, obfuscated_path)
        was_linked = True
    except OSError:
        print(_("  ⚠️ Hardlink falhou. Usando rename."))
        os.replace(input_path, obfuscated_path)
        was_linked = False
    par_input = input_path if was_linked else obfuscated_path
    return obfuscated_path, {random_base: name_no_ext}, was_linked, par_input


def perform_obfuscation(
    input_path: str,
    random_base: Optional[str] = None,
) -> Tuple[str, dict[str, str], bool]:
    """
    Cria visão ofuscada da entrada (hardlinks ou rename).
    Retorna (novo_caminho, obfuscated_map, was_linked).
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        return input_path, {}, False

    parent_dir = os.path.dirname(input_path)
    is_folder = os.path.isdir(input_path)
    base = os.path.basename(input_path)
    name_no_ext = os.path.splitext(base)[0]
    random_base = random_base or generate_random_name()
    is_rar_vol_set = not is_folder and base.endswith(".rar") and ".part" in name_no_ext

    if is_folder:
        obfuscated_path, obfuscated_map, was_linked, _ = _obfuscate_folder(
            input_path, parent_dir, base, random_base
        )
    elif is_rar_vol_set:
        obfuscated_path, obfuscated_map, was_linked, _ = _obfuscate_rar_vol_set(
            input_path, parent_dir, name_no_ext, random_base
        )
    else:
        obfuscated_path, obfuscated_map, was_linked, _ = _obfuscate_single_file(
            input_path, parent_dir, base, random_base
        )

    return obfuscated_path, obfuscated_map, was_linked


def rename_par2_files(
    parent_dir: str, actual_par_input: str, is_rar_vol_set: bool, random_base: str
) -> None:
    """Renomeia .par2 criados com nome original para o nome ofuscado."""
    # Se actual_par_input já for um nome base (string), usa ele.
    # Se for caminho completo, pega o stem.
    if os.sep in actual_par_input or (os.altsep and os.altsep in actual_par_input):
        orig_stem = os.path.splitext(os.path.basename(actual_par_input))[0]
    else:
        orig_stem = os.path.splitext(actual_par_input)[0]

    if is_rar_vol_set:
        orig_stem = orig_stem.rsplit(".part", 1)[0]

    for p_file in glob.glob(os.path.join(parent_dir, glob.escape(orig_stem) + "*.par2")):
        p_base = os.path.basename(p_file)
        # Pega tudo após o stem original (ex: ".vol00+01.par2")
        p_suffix = p_base[len(orig_stem) :]
        new_p_path = os.path.join(parent_dir, random_base + p_suffix)

        if os.path.abspath(p_file) == os.path.abspath(new_p_path):
            continue

        if os.path.exists(new_p_path):
            try:
                os.remove(new_p_path)
            except OSError:
                pass
        try:
            os.replace(p_file, new_p_path)
        except OSError as e:
            print(f"  ⚠️ Falha ao renomear paridade {p_base}: {e}")


def deep_obfuscate_tree(path: str) -> dict[str, str]:
    """Wrapper público para _deep_obfuscate_tree."""
    return _deep_obfuscate_tree(path)


def obfuscate_and_par(
    input_path: str,
    redundancy: Optional[int] = None,
    force: bool = False,
    backend: str = "auto",
    usenet: bool = False,
    post_size: Optional[str] = None,
    threads: Optional[int] = None,
    profile: str = DEFAULT_PROFILE,
    slice_size: Optional[str] = None,
    memory_mb: Optional[int] = None,
    filepath_format: str = "common",
    parpar_extra_args: Optional[list[str]] = None,
    bar: Optional[PhaseBar] = None,
) -> Tuple[int, Optional[str], dict[str, str], bool]:
    """
    Legado: gera paridade e ofusca a entrada.
    Agora refatorado para sempre gerar paridade sobre os nomes originais primeiro.
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        return 2, None, {}, False

    parent_dir = os.path.dirname(input_path)
    is_folder = os.path.isdir(input_path)
    base = os.path.basename(input_path)
    name_no_ext = os.path.splitext(base)[0]
    is_rar_vol_set = not is_folder and base.endswith(".rar") and ".part" in name_no_ext

    # 1. Gera paridade sobre os nomes ORIGINAIS
    rc = make_parity(
        input_path,
        redundancy=redundancy,
        force=force,
        backend=backend,
        usenet=usenet,
        post_size=post_size,
        threads=threads,
        profile=profile,
        slice_size=slice_size,
        memory_mb=memory_mb,
        filepath_format=filepath_format,
        parpar_extra_args=parpar_extra_args,
        bar=bar,
    )

    if rc != 0:
        return rc, None, {}, False

    # 2. Ofusca arquivos
    random_base = generate_random_name()
    try:
        obfuscated_path, obfuscated_map, was_linked = perform_obfuscation(
            input_path, random_base=random_base
        )

        # 3. Renomeia PAR2 para nome aleatório (internamente preserva referências aos nomes reais)
        rename_par2_files(parent_dir, input_path, is_rar_vol_set, random_base)

        # 4. Deep obfuscation
        if is_folder and usenet:
            obfuscated_map.update(deep_obfuscate_tree(obfuscated_path))

        return 0, obfuscated_path, obfuscated_map, was_linked

    except Exception as e:
        print(f"Erro na ofuscação pós-paridade: {e}")
        return 5, None, {}, False


# ── Detecção de backends ──────────────────────────────────────────────────────


def find_par2() -> tuple[str, str] | None:
    for cmd in ("par2", "par2create", "par2.exe", "par2create.exe"):
        path = get_tool_path(cmd)
        if path:
            return ("par2", path)
    return None


def find_parpar() -> tuple[str, str] | None:
    """Procura 'parpar' ou 'par2' no PATH ou pasta bin local."""
    cmds = ["parpar", "parpar.cmd", "parpar.exe", "par2", "par2.exe"]
    for cmd in cmds:
        path = get_tool_path(cmd)
        if path:
            return ("parpar", path)

    # Fallback para node_modules local (comum em CI e dev)
    if sys.platform == "win32":
        # upapasta/upapasta/makepar.py -> upapasta/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_bin = os.path.join(root_dir, "node_modules", ".bin", "parpar.cmd")
        if os.path.exists(local_bin):
            return ("parpar", local_bin)

    return None


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cria arquivos de paridade para um arquivo/pasta (par2/parpar). "
        "O slice size é calculado automaticamente com base no ARTICLE_SIZE do seu .env."
    )
    p.add_argument("rarfile", help="Caminho para o arquivo .rar ou pasta")
    p.add_argument(
        "--profile",
        choices=tuple(PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help=f"Perfil de otimização (padrão: {DEFAULT_PROFILE})",
    )
    p.add_argument(
        "-r",
        "--redundancy",
        type=int,
        default=None,
        help="Redundância em porcentagem (padrão: 10%% para Usenet)",
    )
    p.add_argument("-f", "--force", action="store_true", help="Sobrescrever .par2 existente")
    p.add_argument(
        "--backend",
        choices=("auto", "par2", "parpar"),
        default="auto",
        help="Backend: par2, parpar ou auto (detecta automaticamente, prefere parpar)",
    )
    p.add_argument(
        "--slice-size",
        default=None,
        help=(
            "Sobrescreve o slice size automático (ex: 1M, 1536K). "
            "Se omitido, o script calcula dinamicamente a partir do ARTICLE_SIZE no .env."
        ),
    )
    p.add_argument(
        "--usenet",
        action="store_true",
        help="Flag legada — o comportamento Usenet já é o padrão. Mantida para compatibilidade.",
    )
    p.add_argument(
        "--auto-slice-size",
        action="store_true",
        help="Flag legada — -S do parpar já é sempre ativado. Mantida para compatibilidade.",
    )
    p.add_argument(
        "--post-size",
        default=None,
        help="Flag legada. O slice size agora é derivado de ARTICLE_SIZE, não de post-size.",
    )
    p.add_argument(
        "-t",
        "--threads",
        type=int,
        default=None,
        help="Número de threads (parpar). Padrão: CPUs disponíveis.",
    )
    return p.parse_args()


# ── make_parity ───────────────────────────────────────────────────────────────


def make_parity(
    rar_path: str,
    redundancy: Optional[int] = None,
    force: bool = False,
    backend: str = "auto",
    cmd_template: Optional[str] = None,
    slice_size: Optional[str] = None,
    usenet: bool = False,
    auto_slice_size: bool = False,
    post_size: Optional[str] = None,
    threads: Optional[int] = None,
    profile: str = DEFAULT_PROFILE,
    memory_mb: Optional[int] = None,
    filepath_format: str = "common",
    parpar_extra_args: Optional[list[str]] = None,
    dry_run: bool = False,
    bar: Optional[PhaseBar] = None,
    output_dir: Optional[str] = None,
    input_names: Optional[list[str]] = None,
) -> int:
    """
    Gera arquivos .par2 para rar_path (arquivo único, volume set ou pasta).

    Para parpar, o slice size é calculado automaticamente:
      - Lê ARTICLE_SIZE de ~/.config/upapasta/.env (fallback 768K)
      - base_slice = ARTICLE_SIZE * 2
      - Escala conforme o tamanho total: ≤50GB→base, ≤100GB→1.5x, ≤200GB→2x, >200GB→2.5x
      - Clamp: 1M–4M
      - -S (auto-scaling do parpar) sempre ativo
      - --min-input-slices e --max-input-slices ajustados dinamicamente

    Parâmetros:
      rar_path     : arquivo .rar, primeira parte de um volume set, ou pasta
      redundancy   : percentual de redundância (padrão: 10%)
      force        : sobrescrever .par2 existente
      backend      : 'auto' | 'par2' | 'parpar'
      slice_size   : sobrescreve o cálculo automático (ex: '2M')
      threads      : threads para parpar (None = nº de CPUs)
      profile      : perfil de configuração (fast / balanced / safe)
      memory_mb    : limite de RAM para parpar em MB (None = auto)

    Retorna: 0=ok, 2=entrada inválida, 3=par2 existe, 4=binário não encontrado, 5=erro
    """
    if profile not in PROFILES:
        print(f"Erro: perfil '{profile}' inválido. Opções: {', '.join(PROFILES.keys())}")
        return 2

    profile_config = PROFILES[profile]
    if not isinstance(profile_config, dict):
        profile_config = {}

    if redundancy is None:
        _red = profile_config.get("redundancy", 10)
        redundancy = int(_red) if isinstance(_red, (int, float, str)) else 10

    rar_path = os.path.abspath(rar_path)
    if not os.path.exists(rar_path):
        print(f"Erro: '{rar_path}' não existe.")
        return 2

    is_folder = os.path.isdir(rar_path)
    if not is_folder and not os.path.isfile(rar_path):
        print(f"Erro: '{rar_path}' não é um arquivo nem pasta.")
        return 2

    parent = os.path.dirname(rar_path)
    base = os.path.basename(rar_path)
    name_no_ext = base if is_folder else os.path.splitext(base)[0]

    is_rar_volume_set = (not is_folder) and base.endswith(".rar") and ".part" in name_no_ext
    if is_rar_volume_set:
        name_no_ext = name_no_ext.rsplit(".part", 1)[0]

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_par2 = os.path.join(output_dir, name_no_ext + ".par2")
    else:
        out_par2 = os.path.join(parent, name_no_ext + ".par2")

    if os.path.exists(out_par2) and not force:
        print(f"Erro: '{out_par2}' já existe. Use --force para sobrescrever.")
        return 3

    # ── Coleta de arquivos de entrada ─────────────────────────────────────────
    if is_folder:
        files_to_process = []
        for root, _d, files in os.walk(rar_path):
            for f in files:
                files_to_process.append(os.path.join(root, f))
        if not files_to_process:
            print(f"Erro: pasta '{rar_path}' está vazia.")
            return 2
    elif is_rar_volume_set:
        pattern = os.path.join(parent, glob.escape(name_no_ext) + ".part*.rar")
        files_to_process = sorted(glob.glob(pattern)) or [rar_path]
    else:
        files_to_process = [rar_path]

    # ── Detecção de backend ───────────────────────────────────────────────────
    parpar_found = find_parpar()
    par2_found = find_par2()

    if backend == "parpar":
        if not parpar_found:
            print("Erro: 'parpar' não encontrado no PATH.")
            return 4
        chosen, exe_path = parpar_found
    elif backend == "par2":
        if not par2_found:
            print("Erro: 'par2' não encontrado no PATH.")
            return 4
        chosen, exe_path = par2_found
    else:
        if parpar_found:
            chosen, exe_path = parpar_found
        elif par2_found:
            chosen, exe_path = par2_found
        else:
            print("Erro: nenhum utilitário de paridade ('parpar' ou 'par2') encontrado.")
            return 4

    # ── Cálculo dinâmico de slice (apenas parpar) ─────────────────────────────
    used_slice = slice_size
    min_input_slices = None
    max_input_slices = None
    use_auto_scale = False
    total_bytes = 0

    if chosen == "parpar":
        total_bytes = sum(os.path.getsize(f) for f in files_to_process if os.path.isfile(f))
        if used_slice is None:
            article_size = get_article_size_bytes()
            used_slice, min_input_slices, max_input_slices = compute_dynamic_slice(
                total_bytes, article_size
            )
            if not bar:
                total_gb = total_bytes / (1024**3)
                print(
                    f"  [parpar] ARTICLE_SIZE={fmt_size(article_size)} | "
                    f"total={total_gb:.1f} GB → slice={used_slice} "
                    f"min-slices={min_input_slices} max-slices={max_input_slices}"
                )
        # -S sempre ativo para parpar (auto-scaling garante blocos adequados)
        use_auto_scale = True

    # ── Montagem do comando ───────────────────────────────────────────────────
    if force:
        for f in glob.glob(os.path.join(parent, name_no_ext + "*.par2")):
            try:
                os.remove(f)
            except Exception:
                pass

    if chosen == "parpar":
        cmd = [exe_path, "--progress", "stderr"]
        cmd.append(f"-s{used_slice or '1M'}")
        if use_auto_scale:
            cmd.append("-S")
        # min/max-input-slices apenas para releases grandes o suficiente para satisfazer a restrição
        # (parpar rejeita min-input-slices se o arquivo for menor que slice*min_slices)
        if (
            min_input_slices is not None
            and total_bytes >= parse_size(used_slice or "1M") * min_input_slices
        ):
            cmd.append(f"--min-input-slices={min_input_slices}")
        if max_input_slices is not None:
            cmd.append(f"--max-input-slices={max_input_slices}")

        mem_limit = f"{memory_mb}M" if memory_mb is not None else get_parpar_memory_limit()
        if mem_limit:
            cmd.append(f"-m{mem_limit}")

        num_threads = threads if threads is not None else (os.cpu_count() or 4)
        cmd.extend([f"-t{num_threads}", f"-r{redundancy}%"])
        cmd.extend(["-f", filepath_format])
        if parpar_extra_args:
            cmd.extend(parpar_extra_args)
        cmd.extend(["-o", out_par2])

        # Se temos nomes alternativos (para deofuscação via PAR2), usamos --input-name
        if input_names and len(input_names) == len(files_to_process):
            for orig_name, current_path in zip(input_names, files_to_process):
                cmd.extend(["--input-name", orig_name, current_path])
        else:
            cmd.extend(files_to_process)
    else:
        cmd = [exe_path, "create", f"-r{redundancy}", out_par2] + files_to_process

    # ── Execução ──────────────────────────────────────────────────────────────
    input_desc = (
        f"pasta '{rar_path}' ({len(files_to_process)} arquivo(s))" if is_folder else f"'{rar_path}'"
    )
    msg = _("Criando paridade para {input} -> '{out}' ({red}%)...").format(
        input=input_desc, out=os.path.basename(out_par2), red=redundancy
    )
    if bar:
        bar.log(msg)
    else:
        print(msg)

    if dry_run:
        print("[DRY-RUN] Comando PAR2:")
        print(" ".join(str(x) for x in cmd))
        return 0

    try:
        # managed_popen garante SIGTERM → SIGKILL no filho se receber Ctrl+C
        captured_output: list[str] = []
        with managed_popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0
        ) as proc:
            output_queue: Queue[str | None] = Queue()
            reader_thread = threading.Thread(
                target=_read_output, args=(proc.stdout, output_queue), daemon=True
            )
            reader_thread.start()
            _process_output(output_queue, bar=bar, captured_lines=captured_output)
            rc = proc.wait()

        if rc == 0:
            if not bar:
                print(_("Arquivos de paridade criados com sucesso."))
            return 0
        else:
            error_context = "\n".join(captured_output[-10:])
            if error_context.strip():
                print(_("\n--- Log de erro do PAR2 ({chosen}) ---").format(chosen=chosen))
                for _l in error_context.splitlines():
                    if _l.strip():
                        print(f"  {_l}")
                print("--------------------------------------\n")
            if not bar:
                print(_("Erro: '{chosen}' retornou código {rc}.").format(chosen=chosen, rc=rc))
            return 5
    except KeyboardInterrupt:
        # managed_popen já terminou o filho; propaga para obfuscate_and_par
        # poder reverter a ofuscação antes de sair.
        raise
    except FileNotFoundError:
        print(f"Erro: binário '{chosen}' não encontrado no PATH.")
        return 4
    except PermissionError as e:
        print(f"Erro de permissão ao executar '{chosen}': {e}")
        return 5
    except OSError as e:
        print(f"Erro de I/O ao executar '{chosen}': {e}")
        return 5


def handle_par_failure(
    input_target: str,
    original_rc: int,
    redundancy: Optional[int] = None,
    backend: str = "auto",
    post_size: Optional[str] = None,
    threads: int = 4,
    memory_mb: Optional[int] = None,
    slice_size: Optional[str] = None,
    rar_file: Optional[str] = None,
    par_profile: str = "balanced",
    bar: Optional[PhaseBar] = None,
) -> bool:
    """
    Chamado quando o PAR2 falha. Tenta retry automático com perfil safe
    e threads reduzidas. Se o retry também falhar, preserva os RARs e
    orienta o usuário sobre como retomar.
    """
    if input_target:
        stem = os.path.splitext(input_target)[0]
        if input_target.endswith(".rar") and ".part" in stem:
            stem = stem.rsplit(".part", 1)[0]
        for f in glob.glob(glob.escape(stem) + "*.par2"):
            try:
                os.remove(f)
            except OSError:
                pass

    retry_threads = max(1, min(4, threads // 2))
    retry_profile = "safe"
    retry_memory_mb = max(512, (memory_mb or 2048) // 2)

    print("\n⚠️  Tentando novamente com configurações conservadoras...")
    print(f"   Perfil: {retry_profile} | Threads: {retry_threads} | Memória: {retry_memory_mb} MB")
    print("-" * 60)

    try:
        rc2 = make_parity(
            input_target,
            redundancy=redundancy,
            force=True,
            backend=backend,
            usenet=True,
            post_size=post_size,
            threads=retry_threads,
            profile=retry_profile,
            slice_size=slice_size,
            memory_mb=retry_memory_mb,
            bar=bar,
        )
    except Exception as e:
        print(f"❌ Erro no retry: {e}")
        rc2 = 5

    if rc2 == 0:
        print("-" * 60)
        print(f"✅ Paridade gerada com sucesso no retry (perfil {retry_profile}).")
        return True

    print("-" * 60)
    print(f"\n❌ Falha persistente ao gerar paridade (código original {original_rc}, retry {rc2}).")

    if rar_file:
        rar_base = re.sub(r"\.part\d+$", "", os.path.splitext(rar_file)[0])
        rar_volumes = sorted(glob.glob(glob.escape(rar_base) + ".part*.rar"))
        count = len(rar_volumes)
        print(f"\n📦 Arquivos RAR preservados ({count} parte(s)) em:")
        print(f"   {os.path.dirname(rar_file)}")
        first_rar = rar_volumes[0] if rar_volumes else rar_file
        extra = ""
        if par_profile != "safe":
            extra += " --par-profile safe"
        if threads != retry_threads:
            extra += f" --par-threads {retry_threads}"
        print("\n💡 Para retomar quando o problema for resolvido:")
        print(f"   upapasta {first_rar} --force{extra}")

    return False
