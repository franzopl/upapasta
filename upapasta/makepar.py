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
import shutil
import string
import subprocess
import sys
import threading
from queue import Queue
from typing import Optional, Tuple

from ._process import managed_popen
from ._progress import _read_output, _process_output


# ── Helpers de tamanho ────────────────────────────────────────────────────────

def _parse_size(s: str) -> int:
    """Converte string de tamanho (ex: '700K', '1M', '768000') para bytes."""
    s = str(s).strip()
    if not s:
        raise ValueError("string de tamanho vazia")
    unit = s[-1].upper()
    if unit == 'K':
        return int(float(s[:-1]) * 1024)
    if unit == 'M':
        return int(float(s[:-1]) * 1024 * 1024)
    if unit == 'G':
        return int(float(s[:-1]) * 1024 * 1024 * 1024)
    return int(float(s))


def _fmt_size(b: int) -> str:
    """Formata bytes para string compacta (ex: 1572864 → '1536K' ou '1M')."""
    if b % (1024 * 1024) == 0:
        return f"{b // (1024 * 1024)}M"
    if b % 1024 == 0:
        return f"{b // 1024}K"
    return str(b)


# ── Leitura de ARTICLE_SIZE do .env ──────────────────────────────────────────

def _get_article_size_bytes() -> int:
    """
    Lê ARTICLE_SIZE do ~/.config/upapasta/.env.
    Retorna o valor em bytes. Fallback: 786432 (768K).
    """
    try:
        from .config import load_env_file, DEFAULT_ENV_FILE
        env = load_env_file(DEFAULT_ENV_FILE)
        raw = env.get("ARTICLE_SIZE", "").strip()
        if raw:
            return _parse_size(raw)
    except Exception:
        pass
    return 786432  # 768K


# ── Cálculo dinâmico de slice size ────────────────────────────────────────────

def _compute_dynamic_slice(total_bytes: int, article_size: int) -> Tuple[str, int, int]:
    """
    Calcula slice size, min-input-slices e max-input-slices para parpar.

    Regras:
      base_slice = article_size * 2
      ≤ 50 GB  → base_slice           (min_slices=60)
      ≤ 100 GB → base_slice * 1.5     (min_slices=80)
      ≤ 200 GB → base_slice * 2       (min_slices=100)
      > 200 GB → base_slice * 2.5     (min_slices=120)

    Clamp final: mínimo 1 MiB, máximo 4 MiB.
    max_input_slices fixo em 12000 (limite seguro para NZBGet/SABnzbd).

    Retorna (slice_str, min_slices, max_slices).
    """
    GB = 1024 ** 3
    base = article_size * 2  # ex: 768K → 1.536M

    if total_bytes <= 50 * GB:
        slice_bytes = base
        min_slices = 60
    elif total_bytes <= 100 * GB:
        slice_bytes = int(base * 1.5)
        min_slices = 80
    elif total_bytes <= 200 * GB:
        slice_bytes = base * 2
        min_slices = 100
    else:
        slice_bytes = int(base * 2.5)
        min_slices = 120

    # Clamp: 1 MiB ≤ slice ≤ 4 MiB
    slice_bytes = max(1024 * 1024, min(slice_bytes, 4 * 1024 * 1024))

    return _fmt_size(slice_bytes), min_slices, 12000


# ── Memória disponível ────────────────────────────────────────────────────────

def get_parpar_memory_limit() -> Optional[str]:
    """
    Retorna limite de memória seguro para parpar (75% da RAM livre).
    Mínimo 256M, máximo 3G. Retorna None se não conseguir detectar.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    safe_mb = max(256, min(int((kb // 1024) * 0.75), 3 * 1024))
                    if safe_mb >= 1024 and safe_mb % 1024 == 0:
                        return f"{safe_mb // 1024}G"
                    return f"{safe_mb}M"
    except Exception:
        pass
    return None


from .config import PROFILES, DEFAULT_PROFILE


# ── Obfuscação ────────────────────────────────────────────────────────────────

def generate_random_name(length: int = 12) -> str:
    """Gera um nome de arquivo aleatório com letras e dígitos."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))



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
            
            os.rename(os.path.join(root, f), os.path.join(root, new_name))
            
            new_rel_f = os.path.normpath(os.path.join(rel_root, new_name))
            orig_rel_f = os.path.normpath(os.path.join(orig_rel_root, f))
            mapping[new_rel_f] = orig_rel_f

        # 2. Renomeia diretórios
        for i, d in enumerate(dirs):
            new_name = generate_random_name()
            
            os.rename(os.path.join(root, d), os.path.join(root, new_name))
            
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
    obfuscated_map: dict,
    was_linked: bool = False,
) -> None:
    """
    Reverte a ofuscação (renomeação ou hardlink) dos arquivos do usuário.

    Chamada em qualquer saída anormal de obfuscate_and_par — erro de paridade,
    exceção Python, ou KeyboardInterrupt.
    """
    if was_linked:
        print("  Removendo hardlinks temporários de ofuscação...")
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
            print("  ✓ Hardlinks removidos.")
        except OSError as e:
            print(f"  ✗ Falha ao remover hardlinks: {e}")
        return

    print("  Revertendo ofuscação para restaurar nomes originais...")
    if is_folder:
        try:
            os.rename(obfuscated_path, input_path)
            print(f"  ✓ Pasta restaurada: {os.path.basename(input_path)}")
        except OSError as e:
            print(f"  ✗ Falha ao reverter pasta '{obfuscated_path}' → '{input_path}': {e}")
            print(f"    AÇÃO MANUAL: renomeie '{obfuscated_path}' de volta para '{input_path}'")

    elif is_rar_vol_set and obfuscated_map:
        orig_base = list(obfuscated_map.values())[0]
        vols = sorted(glob.glob(os.path.join(parent_dir, glob.escape(random_base) + ".part*.rar")))
        ok = 0
        for vol in vols:
            suffix = os.path.basename(vol)[len(random_base):]
            original = os.path.join(parent_dir, orig_base + suffix)
            try:
                os.rename(vol, original)
                ok += 1
            except OSError as e:
                print(f"  ✗ Falha ao reverter '{os.path.basename(vol)}' → '{orig_base + suffix}': {e}")
                print(f"    AÇÃO MANUAL: renomeie o arquivo manualmente.")
        if ok:
            print(f"  ✓ {ok} volume(s) RAR restaurado(s): {orig_base}.part*.rar")

    else:
        try:
            os.rename(obfuscated_path, input_path)
            print(f"  ✓ Arquivo restaurado: {os.path.basename(input_path)}")
        except OSError as e:
            print(f"  ✗ Falha ao reverter '{obfuscated_path}' → '{input_path}': {e}")
            print(f"    AÇÃO MANUAL: renomeie '{os.path.basename(obfuscated_path)}' de volta para '{os.path.basename(input_path)}'")


def _obfuscate_folder(
    input_path: str, parent_dir: str, base: str, random_base: str
) -> Tuple[str, dict, bool, str]:
    """Cria visão ofuscada de uma pasta via hardlinks (ou rename fallback)."""
    obfuscated_path = os.path.join(parent_dir, random_base)
    print(f"Ofuscando pasta (hardlink): {base} → {random_base}")
    try:
        link_tree(input_path, obfuscated_path)
        was_linked = True
    except OSError:
        print("  ⚠️ Hardlink falhou (possível cross-device). Usando rename (seeding pode quebrar).")
        os.rename(input_path, obfuscated_path)
        was_linked = False
    return obfuscated_path, {random_base: base}, was_linked, obfuscated_path


def _obfuscate_rar_vol_set(
    input_path: str, parent_dir: str, name_no_ext: str, random_base: str
) -> Tuple[str, dict, bool, str]:
    """Cria visão ofuscada de um conjunto de volumes RAR."""
    original_base = name_no_ext.rsplit(".part", 1)[0]
    volumes = sorted(glob.glob(os.path.join(parent_dir, glob.escape(original_base) + ".part*.rar"))) or [input_path]
    print(f"Ofuscando volumes RAR (hardlink): {original_base}.part*.rar → {random_base}.part*.rar")
    try:
        for vol in volumes:
            suffix = os.path.basename(vol)[len(original_base):]
            os.link(vol, os.path.join(parent_dir, random_base + suffix))
        was_linked = True
    except OSError:
        print("  ⚠️ Hardlink falhou. Usando rename.")
        for v in glob.glob(os.path.join(parent_dir, random_base + ".part*.rar")):
            try:
                os.remove(v)
            except OSError:
                pass
        for vol in volumes:
            suffix = os.path.basename(vol)[len(original_base):]
            os.rename(vol, os.path.join(parent_dir, random_base + suffix))
        was_linked = False
    first_suffix = os.path.basename(volumes[0])[len(original_base):]
    obfuscated_path = os.path.join(parent_dir, random_base + first_suffix)
    return obfuscated_path, {random_base: original_base}, was_linked, obfuscated_path


def _obfuscate_single_file(
    input_path: str, parent_dir: str, base: str, random_base: str
) -> Tuple[str, dict, bool, str]:
    """Cria visão ofuscada de um arquivo único."""
    name_no_ext, ext = os.path.splitext(base)
    obfuscated_path = os.path.join(parent_dir, random_base + ext)
    print(f"Ofuscando (hardlink): {base} → {os.path.basename(obfuscated_path)}")
    try:
        os.link(input_path, obfuscated_path)
        was_linked = True
    except OSError:
        print("  ⚠️ Hardlink falhou. Usando rename.")
        os.rename(input_path, obfuscated_path)
        was_linked = False
    return obfuscated_path, {random_base: name_no_ext}, was_linked, obfuscated_path


def _rename_par2_files(
    parent_dir: str, actual_par_input: str, is_rar_vol_set: bool, random_base: str
) -> None:
    """Renomeia .par2 criados com nome original para o nome ofuscado."""
    orig_stem = os.path.splitext(os.path.basename(actual_par_input))[0]
    if is_rar_vol_set:
        orig_stem = orig_stem.rsplit(".part", 1)[0]
    for p_file in glob.glob(os.path.join(parent_dir, glob.escape(orig_stem) + "*.par2")):
        p_suffix = os.path.basename(p_file)[len(orig_stem):]
        new_p_path = os.path.join(parent_dir, random_base + p_suffix)
        if os.path.exists(new_p_path):
            os.remove(new_p_path)
        os.rename(p_file, new_p_path)


def _cleanup_on_par_failure(
    parent_dir: str,
    random_base: str,
    input_path: str,
    is_rar_vol_set: bool,
    is_folder: bool,
    obfuscated_path: str,
    obfuscated_map: dict,
    was_linked: bool,
) -> None:
    """Remove PAR2 parciais e reverte ofuscação após falha na geração de paridade."""
    print("\nErro ao gerar paridade. Revertendo ofuscação...")
    for par_file in glob.glob(os.path.join(parent_dir, glob.escape(random_base) + "*.par2")):
        try:
            os.remove(par_file)
        except OSError:
            pass
    orig_stem = os.path.splitext(os.path.basename(input_path))[0]
    if is_rar_vol_set:
        orig_stem = orig_stem.rsplit(".part", 1)[0]
    for par_file in glob.glob(os.path.join(parent_dir, glob.escape(orig_stem) + "*.par2")):
        try:
            os.remove(par_file)
        except OSError:
            pass
    _revert_obfuscation(
        is_folder=is_folder,
        is_rar_vol_set=is_rar_vol_set,
        obfuscated_path=obfuscated_path,
        input_path=input_path,
        parent_dir=parent_dir,
        random_base=random_base,
        obfuscated_map=obfuscated_map,
        was_linked=was_linked,
    )


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
    parpar_extra_args: Optional[list] = None,
) -> Tuple[int, Optional[str], dict, bool]:
    """
    Cria visão ofuscada da entrada (hardlinks ou rename) e gera paridade.

    Garante reversão em qualquer saída anormal, inclusive KeyboardInterrupt.
    Retorna (rc, novo_caminho, obfuscated_map, was_linked).
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        print(f"Erro: '{input_path}' não existe.")
        return 2, None, {}, False

    parent_dir = os.path.dirname(input_path)
    is_folder = os.path.isdir(input_path)
    base = os.path.basename(input_path)
    name_no_ext = os.path.splitext(base)[0]
    random_base = generate_random_name()
    is_rar_vol_set = not is_folder and base.endswith(".rar") and ".part" in name_no_ext

    try:
        if is_folder:
            obfuscated_path, obfuscated_map, was_linked, par_input = _obfuscate_folder(
                input_path, parent_dir, base, random_base)
        elif is_rar_vol_set:
            obfuscated_path, obfuscated_map, was_linked, par_input = _obfuscate_rar_vol_set(
                input_path, parent_dir, name_no_ext, random_base)
        else:
            obfuscated_path, obfuscated_map, was_linked, par_input = _obfuscate_single_file(
                input_path, parent_dir, base, random_base)
    except Exception as e:
        print(f"❌ Erro crítico na ofuscação: {e}")
        return 1, None, {}, False

    # Arquivo/volume: gera PAR2 com nome original para que o .par2 grave o nome real.
    # Pasta: usa a cópia ofuscada (link_tree já garantiu nomes originais dentro).
    actual_par_input = input_path if not is_folder else par_input
    _par_succeeded = False
    rc = 5

    try:
        rc = make_parity(
            actual_par_input,
            redundancy=redundancy, force=force, backend=backend, usenet=usenet,
            post_size=post_size, threads=threads, profile=profile,
            slice_size=slice_size, memory_mb=memory_mb,
            filepath_format=filepath_format, parpar_extra_args=parpar_extra_args,
        )
        if rc == 0:
            _par_succeeded = True
            if not is_folder:
                _rename_par2_files(parent_dir, actual_par_input, is_rar_vol_set, random_base)
            if is_folder and usenet and obfuscated_path:
                print("  🔒 Ofuscando estrutura interna (deep obfuscation)...")
                obfuscated_map.update(_deep_obfuscate_tree(obfuscated_path))
    except KeyboardInterrupt:
        raise
    finally:
        if not _par_succeeded and obfuscated_path and obfuscated_map:
            _cleanup_on_par_failure(
                parent_dir, random_base, input_path, is_rar_vol_set,
                is_folder, obfuscated_path, obfuscated_map, was_linked)

    return (0, obfuscated_path, obfuscated_map, was_linked) if rc == 0 else (rc, None, {}, False)



# ── Detecção de backends ──────────────────────────────────────────────────────

def find_par2():
    for cmd in ("par2", "par2create", "par2.exe", "par2create.exe"):
        path = shutil.which(cmd)
        if path:
            return ("par2", path)
    return None


def find_parpar():
    for cmd in ("parpar", "parpar.exe"):
        path = shutil.which(cmd)
        if path:
            return ("parpar", path)
    return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
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
        "-r", "--redundancy",
        type=int, default=None,
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
        "-t", "--threads",
        type=int, default=None,
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
    parpar_extra_args: Optional[list] = None,
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

    if redundancy is None:
        redundancy = profile_config["redundancy"]

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

    out_par2 = os.path.join(parent, name_no_ext + ".par2")

    if os.path.exists(out_par2) and not force:
        print(f"Erro: '{out_par2}' já existe. Use --force para sobrescrever.")
        return 3

    # ── Coleta de arquivos de entrada ─────────────────────────────────────────
    if is_folder:
        files_to_process = []
        for root, _, files in os.walk(rar_path):
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
        total_bytes = sum(
            os.path.getsize(f) for f in files_to_process if os.path.isfile(f)
        )
        if used_slice is None:
            article_size = _get_article_size_bytes()
            used_slice, min_input_slices, max_input_slices = _compute_dynamic_slice(
                total_bytes, article_size
            )
            total_gb = total_bytes / (1024 ** 3)
            print(
                f"  [parpar] ARTICLE_SIZE={_fmt_size(article_size)} | "
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
        cmd = [exe_path]
        cmd.append(f"-s{used_slice or '1M'}")
        if use_auto_scale:
            cmd.append("-S")
        # min/max-input-slices apenas para releases grandes o suficiente para satisfazer a restrição
        # (parpar rejeita min-input-slices se o arquivo for menor que slice*min_slices)
        if min_input_slices is not None and total_bytes >= _parse_size(used_slice or "1M") * min_input_slices:
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
        cmd.extend(files_to_process)
    else:
        cmd = [exe_path, "create", f"-r{redundancy}", out_par2] + files_to_process

    # ── Execução ──────────────────────────────────────────────────────────────
    input_desc = (
        f"pasta '{rar_path}' ({len(files_to_process)} arquivo(s))"
        if is_folder
        else f"'{rar_path}'"
    )
    print(f"Criando paridade para {input_desc} -> '{out_par2}' (redundância {redundancy}%) usando {chosen}...")

    try:
        # managed_popen garante SIGTERM → SIGKILL no filho se receber Ctrl+C
        with managed_popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        ) as proc:
            output_queue: Queue = Queue()
            reader_thread = threading.Thread(
                target=_read_output, args=(proc.stdout, output_queue), daemon=True
            )
            reader_thread.start()
            _process_output(output_queue)
            rc = proc.wait()

        if rc == 0:
            print("Arquivos de paridade criados com sucesso.")
            return 0
        else:
            print(f"Erro: '{chosen}' retornou código {rc}.")
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

    print(f"\n⚠️  Tentando novamente com configurações conservadoras...")
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
        rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(rar_file)[0])
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
        print(f"\n💡 Para retomar quando o problema for resolvido:")
        print(f"   upapasta {first_rar} --force{extra}")

    return False
