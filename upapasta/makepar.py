#!/usr/bin/env python3
"""
makepar.py

Cria arquivos de paridade (.par2) para um arquivo .rar fornecido.

Uso:
  python3 makepar.py arquivo.rar

Opções:
  -r, --redundancy PERCENT   Percentual de redundância (ex: 10 para 10%). Default: varia por perfil
  -f, --force                Sobrescrever arquivos .par2 existentes
  --profile PROFILE          Perfil de otimização: fast, balanced (padrão), safe

Perfis:
  fast                       Máxima velocidade: slice 20M, redundância 5%, post 100M
  balanced                   Equilibrado (PADRÃO): slice 10M, redundância 10%, post 50M
  safe                       Alta proteção: slice 5M, redundância 20%, post 30M

Retornos:
  0: sucesso
  2: arquivo de entrada inválido
  3: arquivo .par2 já existe (use --force)
  4: utilitário 'par2' não encontrado
  5: erro ao executar 'par2'
"""

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


def get_parpar_memory_limit() -> str | None:
    """
    Retorna um limite de memória seguro para o parpar baseado na RAM disponível.
    Usa 75% da RAM livre (MemAvailable no Linux), com mínimo de 256M e máximo de 3G.
    Retorna None se não conseguir detectar.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    available_mb = kb // 1024
                    safe_mb = int(available_mb * 0.75)
                    safe_mb = max(256, min(safe_mb, 3 * 1024))
                    if safe_mb >= 1024 and safe_mb % 1024 == 0:
                        return f"{safe_mb // 1024}G"
                    return f"{safe_mb}M"
    except Exception:
        pass
    return None

from .config import PROFILES, DEFAULT_PROFILE


def generate_random_name(length: int = 12) -> str:
    """Gera um nome de arquivo aleatório com letras e dígitos."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def obfuscate_and_par(
    input_path: str,
    redundancy: int | None = None,
    force: bool = False,
    backend: str = "auto",
    usenet: bool = False,
    post_size: str | None = None,
    threads: int | None = None,
    profile: str = DEFAULT_PROFILE,
    slice_size: str | None = None,
    memory_mb: int | None = None,
) -> tuple[int, str | None, dict[str, str]]:
    """
    Renomeia fisicamente o arquivo/pasta para nome aleatório e gera paridade.

    Retorna (rc, novo_caminho, obfuscated_map) onde obfuscated_map é
    {base_ofuscada: base_original} — usado para nomear o NZB corretamente.
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        print(f"Erro: '{input_path}' não existe.")
        return 2, None, {}

    parent_dir = os.path.dirname(input_path)
    is_folder = os.path.isdir(input_path)
    base = os.path.basename(input_path)
    random_base = generate_random_name()
    obfuscated_map: dict[str, str] = {}

    # ── Pasta ────────────────────────────────────────────────────────────────
    if is_folder:
        obfuscated_path = os.path.join(parent_dir, random_base)
        print(f"Ofuscando pasta: {base} -> {random_base}")
        try:
            os.rename(input_path, obfuscated_path)
        except OSError:
            try:
                shutil.copytree(input_path, obfuscated_path)
                shutil.rmtree(input_path)
            except OSError as e:
                print(f"Erro ao ofuscar pasta: {e}")
                return 1, None, {}
        obfuscated_map[random_base] = base
        par_input = obfuscated_path

    else:
        name_no_ext = os.path.splitext(base)[0]
        is_rar_vol_set = base.endswith(".rar") and ".part" in name_no_ext

        # ── Conjunto de volumes RAR ───────────────────────────────────────────
        if is_rar_vol_set:
            original_base = name_no_ext.rsplit(".part", 1)[0]
            vol_pattern = os.path.join(parent_dir, glob.escape(original_base) + ".part*.rar")
            volumes = sorted(glob.glob(vol_pattern)) or [input_path]

            print(f"Ofuscando {len(volumes)} volumes RAR: {original_base}.part*.rar -> {random_base}.part*.rar")
            renamed: list[tuple[str, str]] = []
            for vol in volumes:
                vol_b = os.path.basename(vol)
                suffix = vol_b[len(original_base):]   # ex: ".part001.rar"
                new_path = os.path.join(parent_dir, random_base + suffix)
                try:
                    os.rename(vol, new_path)
                    renamed.append((vol, new_path))
                except OSError as e:
                    print(f"Erro ao renomear {vol_b}: {e}")
                    for orig, new in renamed:
                        try:
                            os.rename(new, orig)
                        except OSError:
                            pass
                    return 1, None, {}

            obfuscated_map[random_base] = original_base
            first_suffix = os.path.basename(volumes[0])[len(original_base):]
            obfuscated_path = os.path.join(parent_dir, random_base + first_suffix)
            par_input = obfuscated_path

        # ── Arquivo único ─────────────────────────────────────────────────────
        else:
            _, ext = os.path.splitext(base)
            obfuscated_name = random_base + ext
            obfuscated_path = os.path.join(parent_dir, obfuscated_name)
            print(f"Ofuscando: {base} -> {obfuscated_name}")
            try:
                os.rename(input_path, obfuscated_path)
            except OSError:
                try:
                    shutil.copy2(input_path, obfuscated_path)
                    os.remove(input_path)
                except OSError as e:
                    print(f"Erro ao ofuscar arquivo: {e}")
                    return 1, None, {}
            obfuscated_map[random_base] = name_no_ext
            par_input = obfuscated_path

    # ── Gerar paridade nos arquivos já renomeados ─────────────────────────────
    rc = make_parity(
        par_input,
        redundancy=redundancy,
        force=force,
        backend=backend,
        usenet=usenet,
        post_size=post_size,
        threads=threads,
        profile=profile,
        slice_size=slice_size,
        memory_mb=memory_mb,
    )

    if rc == 0:
        return 0, obfuscated_path, obfuscated_map

    # Tentar reverter renomeação
    print("Erro ao gerar paridade. Revertendo ofuscação...")
    if is_folder:
        try:
            os.rename(obfuscated_path, input_path)
        except OSError:
            pass
    elif is_rar_vol_set:
        orig_base_name = list(obfuscated_map.values())[0]
        for vol in sorted(glob.glob(os.path.join(parent_dir, glob.escape(random_base) + ".part*.rar"))):
            suffix = os.path.basename(vol)[len(random_base):]
            try:
                os.rename(vol, os.path.join(parent_dir, orig_base_name + suffix))
            except OSError:
                pass
    else:
        try:
            os.rename(obfuscated_path, input_path)
        except OSError:
            pass
    return rc, None, {}


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


def parse_args():
    p = argparse.ArgumentParser(description="Cria arquivos de paridade para um arquivo .rar (par2/parpar)")
    p.add_argument("rarfile", help="Caminho para o arquivo .rar")
    p.add_argument(
        "--profile",
        choices=tuple(PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help=f"Perfil de otimização (padrão: {DEFAULT_PROFILE})",
    )
    p.add_argument("-r", "--redundancy", type=int, default=None, help="Redundância em porcentagem (sobrescreve perfil)")
    p.add_argument("-f", "--force", action="store_true", help="Sobrescrever .par2 existente")
    p.add_argument(
        "--backend",
        choices=("auto", "par2", "parpar"),
        default="auto",
        help="Escolher backend: par2, parpar ou auto (detecta automaticamente)",
    )
    p.add_argument(
        "--cmd-template",
        default=None,
        help=(
            "Template do comando a executar. Use placeholders: {exe} {out} {rar} {redundancy}. "
            "Se não informado, será usado um template padrão para o backend detectado."
        ),
    )
    p.add_argument(
        "--slice-size",
        default=None,
        help=(
            "Tamanho de slice para ferramentas que suportam (ex: 1M, 512K, 2000). "
            "Se omitido, o template padrão será usado (parpar: 1M)."
        ),
    )
    p.add_argument(
        "--usenet",
        action="store_true",
        help=(
            "Ativa otimização para upload em Usenet: escolhe um slice-size adequado (padrão 1M). "
            "Você pode sobrescrever com --slice-size."
        ),
    )
    p.add_argument(
        "--auto-slice-size",
        action="store_true",
        help=(
            "Quando usado com --backend parpar, ativa o parâmetro -S (auto-slice-size) do parpar "
            "em vez de usar um slice fixo. Se --slice-size for fornecido, este último tem prioridade."
        ),
    )
    p.add_argument(
        "--post-size",
        default="10M",
        help=(
            "Tamanho alvo de post para Usenet (ex: 20M). Usado para calcular um slice-size otimizado. "
            "Padrão: 10M (assumido como padrão do nyuu)."
        ),
    )
    p.add_argument(
        "-t", "--threads",
        type=int,
        default=None,
        help=(
            "Número de threads a usar (parpar). Padrão: número de CPUs disponíveis. "
            "Use 0 ou omita para deixar o parpar decidir automaticamente."
        ),
    )
    return p.parse_args()


def _read_output(pipe, queue: Queue):
	"""Thread worker para ler output do subprocess tratando \r e \n."""
	if pipe is None:
		return
	try:
		buffer = ""
		while True:
			char = pipe.read(1)
			if not char:
				break
			if char in ("\r", "\n"):
				if buffer:
					queue.put(buffer)
					buffer = ""
			else:
				buffer += char
		if buffer:
			queue.put(buffer)
	except:
		pass
	finally:
		queue.put(None)  # Sinal de fim


def _process_output(queue: Queue):
	"""Processa linhas de output da fila na thread principal."""
	bar_width = 25
	spinner = "|/-\\"
	spin_idx = 0
	last_label = ""

	try:
		term_columns = shutil.get_terminal_size().columns
	except Exception:
		term_columns = 80

	while True:
		line = queue.get()
		if line is None:
			break

		line = line.strip()
		if not line:
			continue

		sys.stdout.write("\r" + " " * (term_columns - 1) + "\r")

		# parpar emite "Label: X.X%" — captura label e porcentagem separados
		m = re.match(r"^(.+?):\s*(\d+(?:\.\d+)?)%", line)
		if not m:
			# fallback: qualquer número seguido de %
			m = re.search(r"(\d+(?:\.\d+)?)%", line)
			if m:
				label_part = line[:m.start()].strip().rstrip(":").strip()
				if label_part:
					last_label = label_part
				pct_str = m.group(1)
			else:
				pct_str = None
			label = last_label
		else:
			label = m.group(1).strip()
			pct_str = m.group(2)
			if label:
				last_label = label

		if pct_str is not None:
			try:
				pct_val = float(pct_str)
				filled = int((pct_val / 100.0) * bar_width)
				bar = "#" * filled + "-" * (bar_width - filled)
				prefix = f"[{bar}] {pct_val:5.1f}%"
				# Label vai à direita do prefixo — trunca só o label, nunca a barra
				if last_label:
					available = term_columns - 1 - len(prefix) - 3
					label_trunc = last_label[:available] if available > 0 else ""
					msg = f"{prefix}  {label_trunc}" if label_trunc else prefix
				else:
					msg = prefix
				sys.stdout.write(msg)
				sys.stdout.flush()
				continue
			except ValueError:
				pass

		msg = f"{spinner[spin_idx % len(spinner)]} {line}"
		sys.stdout.write(msg[:term_columns - 1])
		sys.stdout.flush()
		spin_idx += 1

	sys.stdout.write("\n")
	sys.stdout.flush()


def make_parity(rar_path: str, redundancy: int | None = None, force: bool = False, backend: str = 'auto', cmd_template: str | None = None, slice_size: str | None = None, usenet: bool = False, auto_slice_size: bool = False, post_size: str | None = None, threads: int | None = None, profile: str = DEFAULT_PROFILE, memory_mb: int | None = None) -> int:
    # Aplicar configurações do perfil se redundancy ou post_size não foram fornecidos
    if profile not in PROFILES:
        print(f"Erro: perfil '{profile}' inválido. Opções: {', '.join(PROFILES.keys())}")
        return 2
    
    profile_config = PROFILES[profile]
    
    # Se redundância não foi especificada, usar do perfil
    if redundancy is None:
        redundancy = profile_config["redundancy"]
    
    # Se post_size não foi especificado, usar do perfil
    if post_size is None:
        post_size = profile_config["post_size"]
    
    # Se slice_size não foi especificado, usar do perfil
    if slice_size is None:
        slice_size = profile_config["slice_size"]
    
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
    if is_folder:
        name_no_ext = base
    else:
        name_no_ext = os.path.splitext(base)[0]

    # Quando o arquivo é part01.rar de um conjunto de volumes, usar o nome
    # base do conjunto para o PAR2 e processar todas as partes.
    is_rar_volume_set = (not is_folder) and base.endswith(".rar") and ".part" in name_no_ext
    if is_rar_volume_set:
        # ex: "nome.part01" → "nome"
        set_base_name = name_no_ext.rsplit(".part", 1)[0]
        name_no_ext = set_base_name

    out_par2 = os.path.join(parent, name_no_ext + ".par2")

    if os.path.exists(out_par2) and not force:
        print(f"Erro: '{out_par2}' já existe. Use --force para sobrescrever.")
        return 3

    # Collect files to process
    if is_folder:
        files_to_process = []
        for root, dirs, files in os.walk(rar_path):
            for file in files:
                files_to_process.append(os.path.join(root, file))
        if not files_to_process:
            print(f"Erro: pasta '{rar_path}' está vazia.")
            return 2
    elif is_rar_volume_set:
        # Inclui todos os volumes do conjunto ordenados
        pattern = os.path.join(parent, glob.escape(name_no_ext) + ".part*.rar")
        files_to_process = sorted(glob.glob(pattern))
        if not files_to_process:
            files_to_process = [rar_path]
    else:
        files_to_process = [rar_path]

    # Detect backends
    parpar_found = find_parpar()
    par2_found = find_par2()

    chosen = None
    exe_path = None

    if backend == 'parpar':
        if not parpar_found:
            print("Erro: 'parpar' não encontrado no PATH.")
            return 4
        chosen, exe_path = parpar_found
    elif backend == 'par2':
        if not par2_found:
            print("Erro: 'par2' não encontrado no PATH.")
            return 4
        chosen, exe_path = par2_found
    else:  # auto
        if parpar_found:
            chosen, exe_path = parpar_found
        elif par2_found:
            chosen, exe_path = par2_found
        else:
            print("Erro: nenhum utilitário de paridade ('parpar' ou 'par2') encontrado. Instale um deles.")
            return 4

    # Decide slice size: explicit --slice-size > --usenet -> default '1M' > template default
    def parse_size(s: str) -> int:
        """Parse human size like 512K, 1M into bytes (int)."""
        s = str(s).strip()
        if not s:
            raise ValueError("empty size")
        unit = s[-1].upper()
        if unit in ('K', 'M', 'G'):
            try:
                val = float(s[:-1])
            except Exception:
                val = float(s)
            if unit == 'K':
                return int(val * 1024)
            if unit == 'M':
                return int(val * 1024 * 1024)
            if unit == 'G':
                return int(val * 1024 * 1024 * 1024)
        else:
            try:
                return int(s)
            except Exception:
                return int(float(s))
        # fallback
        return int(float(s))

    def fmt_size(b: int) -> str:
        # prefer MiB if divisible, else KiB
        if b % (1024 * 1024) == 0:
            return f"{b // (1024 * 1024)}M"
        if b % 1024 == 0:
            return f"{b // 1024}K"
        return str(b)

    if slice_size:
        used_slice = slice_size
    else:
        # if user provided a post_size or usenet flag, compute slice from post_size
        used_slice = None
        # read post_size from env or default param via parse_args in caller
        # We will attempt to read a global variable POST_SIZE_STR if present, else default '10M'
        post_size_str = post_size or os.environ.get('MAKEPAR_POST_SIZE')
        if not post_size_str:
            post_size_str = '10M'
        try:
            post_size_bytes = parse_size(post_size_str)
        except Exception:
            post_size_bytes = parse_size('10M')

        if usenet or post_size_bytes:
            # Heurística: 4 slices por post garante granularidade razoável para
            # recuperação parcial sem gerar arquivos .par2 excessivamente pequenos.
            # Com post_size=20M → slice=5M; post_size=50M → slice=4M (clamped).
            # Use --par-slice-size para override manual em arquivos muito grandes (50+ GB).
            target_slices = 4
            calc = max(64 * 1024, post_size_bytes // target_slices)
            # clamp: mínimo 64K (par2 exige blocos alinhados), máximo 4M
            calc = min(calc, 4 * 1024 * 1024)
            used_slice = fmt_size(calc)

    # If user supplied a custom cmd_template, use it. Otherwise pick template based on chosen backend
    cmd_t = cmd_template
    if cmd_t is None:
        if chosen == 'parpar':
            if auto_slice_size:
                # If user provided an explicit slice_size, include it and -S to allow autoscaling.
                if used_slice:
                    cmd_t = '{exe} -s{slice_size} -S -r{redundancy}% -o {out} {rar}'
                else:
                    # parpar requires -s; use a reasonable default slice size (1M) together with -S
                    cmd_t = '{exe} -s1M -S -r{redundancy}% -o {out} {rar}'
            else:
                # will build command list directly below
                pass
        else:
            # will build command list directly below
            pass

    # Build command list directly (safer with spaces in paths)
    if chosen == 'parpar':
        cmd = [exe_path]
        if used_slice:
            cmd.extend([f'-s{used_slice}'])
        else:
            cmd.append('-s1M')
        if auto_slice_size:
            cmd.append('-S')
        if memory_mb is not None:
            mem_limit = f"{memory_mb}M"
        else:
            mem_limit = get_parpar_memory_limit()
        if mem_limit:
            cmd.append(f'-m{mem_limit}')
        # Adicionar suporte a multithreading
        num_threads = threads if threads is not None else (os.cpu_count() or 4)
        cmd.extend([f'-t{num_threads}', f'-r{redundancy}%', '-o', out_par2] + files_to_process)
    else:  # par2
        cmd = [exe_path, 'create', f'-r{redundancy}', out_par2] + files_to_process

    # If force requested, remove existing .par2 files matching the base name to allow overwrite
    if force:
        pattern = os.path.join(parent, name_no_ext + '*.par2')
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except Exception:
                pass

    # Mostrar informação sobre threads se for parpar
    input_desc = f"pasta '{rar_path}' ({len(files_to_process)} arquivos)" if is_folder else f"'{rar_path}'"
    print(f"Criando paridade para {input_desc} -> '{out_par2}' (redundância {redundancy}%) usando {chosen}...")

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        # Fila para comunicação entre threads
        output_queue: Queue = Queue()

        # Thread para ler output do subprocess
        reader_thread = threading.Thread(
            target=_read_output,
            args=(proc.stdout, output_queue),
            daemon=True
        )
        reader_thread.start()

        # Processa output na thread principal
        _process_output(output_queue)

        # Aguarda o fim do processo
        rc = proc.wait()
        
        if rc == 0:
            print("Arquivos de paridade criados com sucesso.")
            return 0
        else:
            print(f"Erro: '{chosen}' retornou código {rc}.")
            return 5
    except FileNotFoundError:
        print(f"Erro: binário '{chosen}' não encontrado no PATH.")
        return 4
    except PermissionError as e:
        print(f"Erro de permissão ao executar '{chosen}': {e}")
        return 5
    except OSError as e:
        print(f"Erro de I/O ao executar '{chosen}': {e}")
        return 5



