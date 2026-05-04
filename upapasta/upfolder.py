#!/usr/bin/env python3
"""
upfolder.py

Upload de arquivo .rar e arquivos de paridade (.par2) para Usenet usando nyuu.

Lê credenciais do arquivo .env global (~/.config/upapasta/.env) ou via variáveis de ambiente.

Uso:
  python3 upfolder.py /caminho/para/arquivo.rar

Opções:
  --dry-run              Mostra comando nyuu sem executar
  --nyuu-path PATH       Caminho para executável nyuu (padrão: detecta em PATH)
  --subject SUBJECT      Subject da postagem (padrão: nome do arquivo .rar)
  --group GROUP          Newsgroup para upload (pode sobrescrever .env)

Retornos:
  0: sucesso
  1: arquivo .rar não encontrado
  2: credenciais faltando/inválidas
  3: arquivo .par2 não encontrado
  4: nyuu não encontrado
  5: erro ao executar nyuu
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
import time
import xml.etree.ElementTree as ET
from typing import Optional

from .nzb import resolve_nzb_out, handle_nzb_conflict, fix_nzb_subjects, inject_nzb_password
from upapasta import nfo
from ._process import managed_popen


_NYUU_ERRORS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"40[13]", re.I), "Erro de autenticação (401/403): verifique usuário e senha no .env"),
    (re.compile(r"502", re.I), "Servidor indisponível (502): tente novamente mais tarde"),
    (re.compile(r"441", re.I), "Artigo rejeitado pelo servidor (441): verifique permissões da conta"),
    (re.compile(r"timeout", re.I), "Timeout de conexão: verifique host/porta e sua conexão de internet"),
    (re.compile(r"ECONNREFUSED|connection refused", re.I), "Conexão recusada: verifique NNTP_HOST e NNTP_PORT"),
    (re.compile(r"ENOTFOUND|getaddrinfo", re.I), "Host não encontrado: verifique NNTP_HOST no .env"),
    (re.compile(r"certificate|SSL|TLS", re.I), "Erro de certificado SSL: use NNTP_IGNORE_CERT=true para contornar"),
]


def _parse_nyuu_stderr(stderr: str) -> str | None:
    """Traduz mensagens de erro do nyuu para português. Retorna None se não reconhecido."""
    for pattern, msg in _NYUU_ERRORS:
        if pattern.search(stderr):
            return msg
    return None


def _verify_nzb(nzb_path: str) -> bool:
    """Verifica que o NZB existe, não está vazio e contém ao menos um elemento <file>."""
    if not os.path.exists(nzb_path):
        return False
    if os.path.getsize(nzb_path) == 0:
        return False
    try:
        tree = ET.parse(nzb_path)
        root = tree.getroot()
        # Suporta NZB com ou sem namespace
        files = root.findall('.//{http://www.newzbin.com/DTD/2003/nzb}file') or root.findall('.//file')
        return len(files) > 0
    except ET.ParseError:
        return False


def find_nyuu() -> Optional[str]:
    """Procura executável 'nyuu' no PATH."""
    for cmd in ("nyuu", "nyuu.exe"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def parse_args():
    p = argparse.ArgumentParser(
        description="Upload de .rar + .par2 para Usenet com nyuu"
    )
    p.add_argument("rarfile", help="Caminho para o arquivo .rar a fazer upload")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra comando nyuu sem executar",
    )
    p.add_argument(
        "--nyuu-path",
        default=None,
        help="Caminho para executável nyuu (padrão: detecta em PATH)",
    )
    p.add_argument(
        "--subject",
        default=None,
        help="Subject da postagem (padrão: nome do arquivo .rar)",
    )
    p.add_argument(
        "--group",
        default=None,
        help="Newsgroup (pode sobrescrever variável USENET_GROUP do .env)",
    )
    p.add_argument(
        "--env-file",
        default=os.path.expanduser("~/.config/upapasta/.env"),
        help="Caminho para arquivo .env (padrão: ~/.config/upapasta/.env)",
    )
    return p.parse_args()


def generate_anonymous_uploader() -> str:
    """Gera um nome de uploader aleatório e anônimo para proteger privacidade."""
    first_names = [
        "Anonymous", "User", "Poster", "Uploader", "Contributor", "Member",
        "Guest", "Visitor", "Participant", "Sender", "Provider", "Supplier"
    ]
    suffix = ''.join(random.choices(string.digits, k=4))
    name = random.choice(first_names)
    domains = ["anonymous.net", "upload.net", "poster.com", "user.org", "generic.mail"]
    domain = random.choice(domains)
    return f"{name}{suffix} <{name}{suffix}@{domain}>"


def upload_to_usenet(
    input_path: str,
    env_vars: dict,
    dry_run: bool = False,
    nyuu_path: Optional[str] = None,
    subject: Optional[str] = None,
    group: Optional[str] = None,
    skip_rar: bool = False,
    obfuscated_map: Optional[dict] = None,
    upload_timeout: Optional[int] = None,
    upload_retries: int = 0,
    password: Optional[str] = None,
    nyuu_extra_args: Optional[list] = None,
    folder_name: Optional[str] = None,
) -> int:
    """
    Upload de arquivos para Usenet usando nyuu.

    Para pastas (skip_rar=True ou entrada é diretório), o nyuu é invocado com
    cwd=input_path e caminhos de arquivo relativos, evitando completamente a cópia
    dos dados para /tmp. Os arquivos PAR2 ficam no diretório pai e são passados
    com caminhos absolutos (nyuu aceita mistura de relativos e absolutos).
    """

    input_path = os.path.abspath(input_path)

    # Validar entrada
    if not os.path.exists(input_path):
        print(f"Erro: '{input_path}' não existe.")
        return 1

    is_folder = os.path.isdir(input_path)
    if not is_folder and not os.path.isfile(input_path):
        print(f"Erro: '{input_path}' não é um arquivo nem pasta.")
        return 1

    # ── Construir lista de arquivos e working_dir ────────────────────────────
    #
    # CASO 1 — pasta (skip_rar ou input direto de pasta):
    #   working_dir = input_path
    #   files_to_upload = caminhos relativos de TODOS os arquivos dentro da pasta
    #   par2_files = caminhos ABSOLUTOS (ficam no diretório pai da pasta)
    #
    # CASO 2 — arquivo único ou conjunto de volumes RAR:
    #   working_dir = diretório pai do arquivo
    #   files_to_upload = basename(s) do(s) arquivo(s)
    #   par2_files = basenames dos .par2 (mesmo diretório)
    #
    # Nenhuma cópia é feita em nenhum dos dois casos.

    if is_folder:
        working_dir = input_path
        parent_dir = os.path.dirname(input_path)

        # Caminhos relativos de todos os arquivos dentro da pasta
        files_to_upload: list = []
        for root, _, files in os.walk(input_path):
            for file in sorted(files):
                abs_file = os.path.join(root, file)
                rel_path = os.path.relpath(abs_file, input_path)
                files_to_upload.append(rel_path)

        # PAR2 fica no diretório pai — passamos caminhos absolutos
        base_name = input_path
        par2_pattern = glob.escape(base_name) + "*par2*"
        par2_files: list = sorted(glob.glob(par2_pattern))
        # par2_files já são absolutos (resultado de glob com caminho absoluto)

    else:
        working_dir = os.path.dirname(input_path)
        parent_dir = working_dir

        base_no_ext = os.path.splitext(os.path.basename(input_path))[0]
        is_rar_volume = input_path.endswith(".rar") and ".part" in base_no_ext

        if is_rar_volume:
            # Conjunto de volumes: inclui todos os partXX.rar do conjunto
            set_base = base_no_ext.rsplit(".part", 1)[0]
            vol_pattern = os.path.join(working_dir, glob.escape(set_base) + ".part*.rar")
            rar_volumes = sorted(glob.glob(vol_pattern))
            files_to_upload = [os.path.basename(v) for v in rar_volumes] if rar_volumes else [os.path.basename(input_path)]
            base_name = os.path.join(working_dir, set_base)
        else:
            files_to_upload = [os.path.basename(input_path)]
            base_name = os.path.splitext(input_path)[0]

        par2_pattern = glob.escape(base_name) + "*par2*"
        par2_files = sorted(glob.glob(par2_pattern))
        # Para arquivos, par2_files contêm caminhos absolutos também (resultado de glob)
        # Convertemos para basename pois o working_dir é o mesmo diretório
        par2_files = [os.path.basename(f) for f in par2_files]

    if not par2_files:
        print(f"Erro: nenhum arquivo de paridade encontrado para '{input_path}'.")
        print("Execute 'python3 makepar.py' primeiro para gerar os arquivos .par2")
        return 3

    # Carrega credenciais
    nntp_host = env_vars.get("NNTP_HOST") or os.environ.get("NNTP_HOST")
    nntp_port = env_vars.get("NNTP_PORT") or os.environ.get("NNTP_PORT", "119")
    nntp_ssl = env_vars.get("NNTP_SSL", "false").lower() in ("true", "1", "yes")
    nntp_ignore_cert = env_vars.get("NNTP_IGNORE_CERT", "false").lower() in ("true", "1", "yes")
    nntp_user = env_vars.get("NNTP_USER") or os.environ.get("NNTP_USER")
    nntp_pass = env_vars.get("NNTP_PASS") or os.environ.get("NNTP_PASS")
    nntp_connections = env_vars.get("NNTP_CONNECTIONS") or os.environ.get("NNTP_CONNECTIONS", "50")
    usenet_group = group or env_vars.get("USENET_GROUP") or os.environ.get("USENET_GROUP")
    
    # Pool de grupos: seleciona um grupo aleatório por upload para distribuir
    # o histórico entre múltiplos grupos e dificultar remoção seletiva.
    if usenet_group and "," in usenet_group:
        groups = [g.strip() for g in usenet_group.split(",") if g.strip()]
        if groups:
            usenet_group = random.choice(groups)
    article_size = env_vars.get("ARTICLE_SIZE") or os.environ.get("ARTICLE_SIZE", "700K")
    check_connections = env_vars.get("CHECK_CONNECTIONS") or os.environ.get("CHECK_CONNECTIONS", "5")
    check_tries = env_vars.get("CHECK_TRIES") or os.environ.get("CHECK_TRIES", "2")
    check_delay = env_vars.get("CHECK_DELAY") or os.environ.get("CHECK_DELAY", "5s")
    check_retry_delay = env_vars.get("CHECK_RETRY_DELAY") or os.environ.get("CHECK_RETRY_DELAY", "30s")
    check_post_tries = env_vars.get("CHECK_POST_TRIES") or os.environ.get("CHECK_POST_TRIES", "2")
    nzb_overwrite_env = env_vars.get("NZB_OVERWRITE") or os.environ.get("NZB_OVERWRITE")
    skip_errors = env_vars.get("SKIP_ERRORS") or os.environ.get("SKIP_ERRORS", "all")
    dump_failed_posts = env_vars.get("DUMP_FAILED_POSTS") or os.environ.get("DUMP_FAILED_POSTS")
    quiet = env_vars.get("QUIET", "false").lower() in ("true", "1", "yes")
    log_time = env_vars.get("LOG_TIME", "true").lower() in ("true", "1", "yes")

    # Args extras do .env
    env_nyuu_args = env_vars.get("NYUU_EXTRA_ARGS")
    if env_nyuu_args and nyuu_extra_args is None:
        import shlex
        nyuu_extra_args = shlex.split(env_nyuu_args)

    nzb_out_dir = env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR")
    nzb_out, nzb_out_abs = resolve_nzb_out(
        input_path, env_vars, is_folder, skip_rar, nzb_out_dir or working_dir, obfuscated_map
    )
    nzb_out, nzb_out_abs, nzb_overwrite, ok = handle_nzb_conflict(
        nzb_out, nzb_out_abs, env_vars, nzb_overwrite_env, nzb_out_dir or working_dir
    )
    if not ok:
        return 6

    if not all([nntp_host, nntp_user, nntp_pass, usenet_group]):
        print("Erro: credenciais incompletas. Configure .env com:")
        print("  NNTP_HOST=<seu_servidor>")
        print("  NNTP_PORT=119")
        print("  NNTP_USER=<seu_usuario>")
        print("  NNTP_PASS=<sua_senha>")
        print("  USENET_GROUP=<seu_grupo>")
        return 2

    # Encontra nyuu
    if nyuu_path:
        if not os.path.exists(nyuu_path):
            print(f"Erro: nyuu não encontrado em '{nyuu_path}'")
            return 4
    else:
        nyuu_path = find_nyuu()
        if not nyuu_path:
            print("Erro: nyuu não encontrado. Instale-o (https://github.com/Piorosen/nyuu)")
            return 4

    # Define subject
    if not subject:
        if is_folder:
            subject = os.path.basename(input_path)
        else:
            subject = os.path.basename(os.path.splitext(input_path)[0])

    # Geração de NFO para arquivo único (se não for pasta e tivermos caminho de NZB)
    # Isso garante que mesmo o upload direto via upfolder.py gere metadados.
    if not is_folder and nzb_out_abs:
        nfo_path = os.path.abspath(os.path.splitext(nzb_out_abs)[0] + ".nfo")
        if not os.path.exists(nfo_path):
            mediainfo_path = nfo.find_mediainfo()
            if mediainfo_path:
                try:
                    proc = subprocess.run([mediainfo_path, input_path], capture_output=True, text=True, check=True)
                    with open(nfo_path, "w", encoding="utf-8") as f:
                        f.write(proc.stdout)
                except Exception:
                    pass

    # Constrói comando nyuu
    cmd = [
        nyuu_path,
        "-h", nntp_host,
        "-P", str(nntp_port),
    ]

    if nntp_ssl:
        cmd.append("-S")

    if nntp_ignore_cert:
        cmd.append("-i")

    cmd.extend([
        "-u", nntp_user,
        "-p", nntp_pass,
        "-n", str(nntp_connections),
        "-g", usenet_group,
        "-a", article_size,
        "-f", generate_anonymous_uploader(),
        "--date", "now",
        "-t", subject,
    ])

    if nzb_out:
        cmd.extend(["-o", nzb_out_abs])
        # Garantir que o diretório de saída do NZB existe
        if nzb_out_abs:
            os.makedirs(os.path.dirname(nzb_out_abs), exist_ok=True)

    if nzb_overwrite:
        cmd.append("-O")

    if upload_timeout is not None:
        cmd.extend(["--timeout", str(upload_timeout)])

    if nyuu_extra_args:
        cmd.extend(nyuu_extra_args)

    # ── Adicionar arquivos ao comando ────────────────────────────────────────
    #
    # Para pastas: files_to_upload são relativos a working_dir (=input_path)
    #              par2_files são absolutos (diretório pai)
    # Para arquivos: tudo relativo a working_dir (mesmo diretório)
    #
    # O obfuscated_map controla o subject/NZB mas NÃO altera os caminhos físicos
    # passados ao nyuu — o nyuu usa o caminho físico real, o NZB é corrigido
    # depois pela função fix_nzb_subjects.

    cmd.extend(files_to_upload)
    cmd.extend(par2_files)

    # ── Calcular tamanho total para exibição ─────────────────────────────────
    total_size_bytes = 0
    for f in files_to_upload:
        try:
            total_size_bytes += os.path.getsize(os.path.join(working_dir, f))
        except OSError:
            pass
    for f in par2_files:
        try:
            # par2_files para pastas são absolutos; para arquivos são basenames
            if os.path.isabs(f):
                total_size_bytes += os.path.getsize(f)
            else:
                total_size_bytes += os.path.getsize(os.path.join(working_dir, f))
        except OSError:
            pass

    all_file_count = len(files_to_upload) + len(par2_files)

    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.2f} MB"
        else:
            return f"{size_bytes/1024**3:.2f} GB"

    try:
        term_columns = shutil.get_terminal_size().columns
    except Exception:
        term_columns = 80
    sep = "─" * min(term_columns - 1, 60)

    rows = [
        ("Host",    f"{nntp_host}:{nntp_port}"),
        ("Grupo",   usenet_group),
        ("Subject", subject),
        ("Total",   f"{format_size(total_size_bytes)}  ({all_file_count} arquivos)"),
    ]
    if nzb_out:
        rows.append(("NZB", nzb_out))

    label_w = max(len(r[0]) for r in rows)
    print(sep)
    print("  Upload para Usenet")
    print(sep)
    for label, value in rows:
        print(f"  {label:<{label_w}}  {value}")
    print(sep)
    print()

    if dry_run:
        print("Comando nyuu (dry-run):")
        print(" ".join(str(x) for x in cmd))
        return 0

    # ── Executar nyuu ────────────────────────────────────────────────────────
    # managed_popen garante SIGTERM → SIGKILL no nyuu se receber Ctrl+C.
    # Retry com backoff exponencial: 30s → 90s → 270s (+jitter ±10%).
    max_attempts = 1 + max(0, upload_retries)
    last_rc = 5
    _BACKOFF_BASE = 30  # segundos

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            delay = _BACKOFF_BASE * (3 ** (attempt - 2))
            jitter = int(delay * 0.10 * (random.random() * 2 - 1))
            wait = max(1, delay + jitter)
            print(f"\n⏳ Aguardando {wait}s antes da tentativa {attempt}/{max_attempts}...")
            time.sleep(wait)
            print(f"\nTentativa {attempt}/{max_attempts} de upload...")
        try:
            with managed_popen(cmd, cwd=working_dir) as proc:
                last_rc = proc.wait()

            stderr_data = ""
            if last_rc == 0:
                break
            print(f"\nErro: nyuu retornou código {last_rc}.")
            if stderr_data:
                friendly = _parse_nyuu_stderr(stderr_data)
                if friendly:
                    print(f"  → {friendly}")
                else:
                    # Exibe últimas 3 linhas do stderr para diagnóstico
                    lines = [ln for ln in stderr_data.strip().splitlines() if ln.strip()][-3:]
                    if lines:
                        print("  Saída do nyuu:")
                        for line in lines:
                            print(f"    {line}")
        except KeyboardInterrupt:
            # managed_popen já matou o nyuu; propaga para o orquestrador
            raise
        except FileNotFoundError:
            print(f"\nErro: nyuu não encontrado em '{nyuu_path}'.")
            return 4
        except OSError as e:
            print(f"\nErro de I/O ao executar nyuu: {e}")
            last_rc = 5

    if last_rc != 0:
        return last_rc

    # ── Pós-processamento do NZB ─────────────────────────────────────────────

    # Corrigir subjects no NZB para preservar estrutura de pastas e deofuscar.
    # files_to_upload contém os caminhos relativos usados pelo nyuu; o NZB
    # terá esses mesmos nomes como subjects — fix_nzb_subjects os remapeia.
    if nzb_out_abs and os.path.exists(nzb_out_abs) and (is_folder or obfuscated_map or folder_name):
        # Os par2 passados ao nyuu eram absolutos; para o NZB só seus basenames
        # interessam.
        par2_basenames = [os.path.basename(f) for f in par2_files]
        fix_nzb_subjects(nzb_out_abs, files_to_upload + par2_basenames, folder_name, obfuscated_map)

    # Injetar senha no NZB para extração automática pelos clientes
    if nzb_out_abs and os.path.exists(nzb_out_abs) and password and not skip_rar:
        inject_nzb_password(nzb_out_abs, password)
        print("Senha injetada no NZB.")

    # Verificar integridade do NZB gerado
    if nzb_out_abs:
        if not _verify_nzb(nzb_out_abs):
            print(f"Aviso: NZB gerado em '{nzb_out_abs}' está ausente, vazio ou não contém elementos <file>.")
        else:
            print(f"NZB verificado: {os.path.basename(nzb_out_abs)}")

    return 0
