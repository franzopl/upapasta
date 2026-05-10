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
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from queue import Queue
from typing import TYPE_CHECKING, Optional

from upapasta import nfo

from ._process import managed_popen
from ._progress import _process_output, _read_output
from .i18n import _

if TYPE_CHECKING:
    from .ui import PhaseBar
from .nzb import (
    fix_nzb_subjects,
    handle_nzb_conflict,
    inject_nzb_password,
    merge_nzbs,
    resolve_nzb_out,
)

_NYUU_ERRORS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"40[13]", re.I),
        _("Erro de autenticação (401/403): verifique usuário e senha no .env"),
    ),
    (re.compile(r"502", re.I), _("Servidor indisponível (502): tente novamente mais tarde")),
    (
        re.compile(r"441", re.I),
        _("Artigo rejeitado pelo servidor (441): verifique permissões da conta"),
    ),
    (
        re.compile(r"timeout", re.I),
        _("Timeout de conexão: verifique host/porta e sua conexão de internet"),
    ),
    (
        re.compile(r"ECONNREFUSED|connection refused", re.I),
        _("Conexão recusada: verifique NNTP_HOST e NNTP_PORT"),
    ),
    (
        re.compile(r"ENOTFOUND|getaddrinfo", re.I),
        _("Host não encontrado: verifique NNTP_HOST no .env"),
    ),
    (
        re.compile(r"certificate|SSL|TLS", re.I),
        _("Erro de certificado SSL: use NNTP_IGNORE_CERT=true para contornar"),
    ),
]


def _build_server_list(env_vars: dict[str, str]) -> list[dict[str, object]]:
    """Constrói lista de configs de servidor NNTP a partir do env.

    Servidor primário: NNTP_HOST, NNTP_PORT, NNTP_USER, NNTP_PASS, ...
    Servidores adicionais: NNTP_HOST_2, NNTP_PORT_2, ... NNTP_HOST_9, ...
    Campos não definidos para servidores adicionais herdam do primário.
    """

    def _bool(val: str, default: bool = False) -> bool:
        return val.lower() in ("true", "1", "yes") if val else default

    primary_host = env_vars.get("NNTP_HOST") or os.environ.get("NNTP_HOST", "")
    servers: list[dict[str, object]] = []
    if primary_host:
        servers.append(
            {
                "host": primary_host,
                "port": env_vars.get("NNTP_PORT") or os.environ.get("NNTP_PORT", "119"),
                "ssl": _bool(env_vars.get("NNTP_SSL", "") or os.environ.get("NNTP_SSL", "")),
                "ignore_cert": _bool(
                    env_vars.get("NNTP_IGNORE_CERT", "") or os.environ.get("NNTP_IGNORE_CERT", "")
                ),
                "user": env_vars.get("NNTP_USER") or os.environ.get("NNTP_USER", ""),
                "password": env_vars.get("NNTP_PASS") or os.environ.get("NNTP_PASS", ""),
                "connections": env_vars.get("NNTP_CONNECTIONS")
                or os.environ.get("NNTP_CONNECTIONS", "50"),
            }
        )

    for i in range(2, 10):
        host = env_vars.get(f"NNTP_HOST_{i}") or os.environ.get(f"NNTP_HOST_{i}", "")
        if not host:
            break
        p = servers[0] if servers else {}
        servers.append(
            {
                "host": host,
                "port": env_vars.get(f"NNTP_PORT_{i}")
                or os.environ.get(f"NNTP_PORT_{i}")
                or p.get("port", "119"),
                "ssl": _bool(
                    env_vars.get(f"NNTP_SSL_{i}") or os.environ.get(f"NNTP_SSL_{i}", ""),
                    default=bool(p.get("ssl", False)),
                ),
                "ignore_cert": _bool(
                    env_vars.get(f"NNTP_IGNORE_CERT_{i}")
                    or os.environ.get(f"NNTP_IGNORE_CERT_{i}", "")
                ),
                "user": env_vars.get(f"NNTP_USER_{i}")
                or os.environ.get(f"NNTP_USER_{i}")
                or p.get("user", ""),
                "password": env_vars.get(f"NNTP_PASS_{i}")
                or os.environ.get(f"NNTP_PASS_{i}")
                or p.get("password", ""),
                "connections": env_vars.get(f"NNTP_CONNECTIONS_{i}")
                or os.environ.get(f"NNTP_CONNECTIONS_{i}")
                or p.get("connections", "50"),
            }
        )

    return servers


def _get_uploaded_files_from_nzb(nzb_path: str) -> set[str]:
    """Lê NZB parcial e retorna o conjunto de nomes de arquivo já postados."""
    if not os.path.exists(nzb_path) or os.path.getsize(nzb_path) == 0:
        return set()
    try:
        tree = ET.parse(nzb_path)
        root = tree.getroot()
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        files = root.findall(f".//{{{ns}}}file") or root.findall(".//file")
        names: set[str] = set()
        for f in files:
            subject = f.get("subject", "")
            m = re.search(r'"([^"]+)"', subject)
            if m:
                names.add(m.group(1))
        return names
    except Exception:
        return set()


def _save_upload_state(
    state_path: str, files: list[str], par2_files: list[str], working_dir: str, nzb_out_abs: str
) -> None:
    """Salva estado do upload para permitir retomada em caso de interrupção."""
    import hashlib
    import json as _json

    content_hash = hashlib.sha256("\n".join(sorted(files)).encode()).hexdigest()[:16]
    state = {
        "version": 1,
        "content_hash": content_hash,
        "files": files,
        "par2_files": par2_files,
        "working_dir": working_dir,
        "nzb_out": nzb_out_abs,
    }
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as fh:
            _json.dump(state, fh, indent=2)
    except Exception as e:
        print(_("Aviso: não foi possível salvar estado de upload: {error}").format(error=e))


def _load_upload_state(state_path: str) -> dict[str, object] | None:
    import json as _json

    try:
        with open(state_path, encoding="utf-8") as fh:
            data = _json.load(fh)
            if not isinstance(data, dict):
                return None
            return data
    except Exception:
        return None


def _article_size_to_bytes(article_size: str) -> int:
    """Converte string de tamanho de artigo ('700K', '1M', '750000') para bytes."""
    s = article_size.strip().upper()
    if s.endswith("K"):
        return int(float(s[:-1]) * 1024)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1024 * 1024)
    return int(s)


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
        files = root.findall(".//{http://www.newzbin.com/DTD/2003/nzb}file") or root.findall(
            ".//file"
        )
        return len(files) > 0
    except ET.ParseError:
        return False


def find_nyuu() -> Optional[str]:
    """Procura executável 'nyuu' no PATH."""
    cmds = ["nyuu", "nyuu.cmd", "nyuu.exe"]
    for cmd in cmds:
        path = shutil.which(cmd)
        if path:
            return path

    # Fallback para node_modules local (comum em CI e dev)
    if sys.platform == "win32":
        # upapasta/upapasta/upfolder.py -> upapasta/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_bin = os.path.join(root_dir, "node_modules", ".bin", "nyuu.cmd")
        if os.path.exists(local_bin):
            return local_bin

    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=_("Upload de .rar + .par2 para Usenet com nyuu"))
    p.add_argument("rarfile", help=_("Caminho para o arquivo .rar a fazer upload"))
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=_("Mostra comando nyuu sem executar"),
    )
    p.add_argument(
        "--nyuu-path",
        default=None,
        help=_("Caminho para executável nyuu (padrão: detecta em PATH)"),
    )
    p.add_argument(
        "--subject",
        default=None,
        help=_("Subject da postagem (padrão: nome do arquivo .rar)"),
    )
    p.add_argument(
        "--group",
        default=None,
        help=_("Newsgroup (pode sobrescrever variável USENET_GROUP do .env)"),
    )
    p.add_argument(
        "--env-file",
        default=os.path.expanduser("~/.config/upapasta/.env"),
        help=_("Caminho para arquivo .env (padrão: ~/.config/upapasta/.env)"),
    )
    return p.parse_args()


def _create_nyuu_fragmentation_config(groups: list[str]) -> str:
    """Cria um arquivo JS temporário para o nyuu rotacionar grupos por artigo.

    Esta é a técnica de fragmentação multigrupo (Cross-Group Fragmentation).
    """
    import tempfile

    js_content = f"""
module.exports = {{
    newsgroups: function(article, file) {{
        var groups = {json.dumps(groups)};
        // Rotaciona o grupo baseado no número da parte do artigo
        return groups[article.part % groups.length];
    }}
}};
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js_content)
        return f.name


def jitter_article_size(size_str: str) -> str:
    """Adiciona um 'jitter' (variação aleatória) ao tamanho do artigo.

    Ex: '700K' -> 716800 +/- 5000 bytes. Retorna o valor em bytes como string.
    """
    try:
        base_bytes = _article_size_to_bytes(size_str)
        # Variação de +/- 1% (máximo 10KB)
        variation = int(base_bytes * 0.01)
        jitter = random.randint(-variation, variation)
        return str(base_bytes + jitter)
    except Exception:
        return size_str


def generate_anonymous_uploader() -> str:
    """Gera um nome de uploader aleatório e anônimo para proteger privacidade.

    Usa a filosofia Schizo de comprimentos e domínios variáveis.
    """
    from .makepar import generate_random_name

    prefix_names = [
        "Anonymous",
        "User",
        "Poster",
        "Uploader",
        "Contributor",
        "Member",
        "Guest",
        "Visitor",
        "Participant",
        "Sender",
        "Provider",
        "Supplier",
    ]
    name = random.choice(prefix_names)
    # Variabilidade Schizo no sufixo e no nome do uploader
    suffix = "".join(random.choices(string.digits, k=random.randint(4, 8)))
    real_name = f"{name}{suffix}"

    # Domínios variados e aleatórios
    domains = [
        "anonymous.net",
        "upload.net",
        "poster.com",
        "user.org",
        "generic.mail",
        "usenet.net",
        "binaries.net",
        "hidden.org",
    ]
    # Às vezes usa um domínio totalmente aleatório (Schizo level 2)
    if random.random() < 0.3:
        domain = f"{generate_random_name(5, 10)}.{random.choice(['com', 'net', 'org', 'io'])}"
    else:
        domain = random.choice(domains)

    return f"{real_name} <{real_name}@{domain}>"


def upload_to_usenet(
    input_path: str,
    env_vars: dict[str, str],
    dry_run: bool = False,
    nyuu_path: Optional[str] = None,
    subject: Optional[str] = None,
    group: Optional[str] = None,
    skip_rar: bool = False,
    obfuscated_map: Optional[dict[str, str]] = None,
    upload_timeout: Optional[int] = None,
    upload_retries: int = 0,
    password: Optional[str] = None,
    nyuu_extra_args: Optional[list[str]] = None,
    folder_name: Optional[str] = None,
    resume: bool = False,
    bar: Optional[PhaseBar] = None,
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
        print(_("Erro: '{path}' não existe.").format(path=input_path))
        return 1

    is_folder = os.path.isdir(input_path)
    if not is_folder and not os.path.isfile(input_path):
        print(_("Erro: '{path}' não é um arquivo nem pasta.").format(path=input_path))
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

        # Caminhos relativos de todos os arquivos dentro da pasta
        files_to_upload: list[str] = []
        for root, _d, files in os.walk(input_path):
            for file in sorted(files):
                abs_file = os.path.join(root, file)
                rel_path = os.path.relpath(abs_file, input_path)
                files_to_upload.append(rel_path)

        # PAR2 fica no diretório pai — passamos caminhos absolutos
        base_name = input_path
        par2_pattern = glob.escape(base_name) + "*par2*"
        par2_files: list[str] = sorted(glob.glob(par2_pattern))
        # par2_files já são absolutos (resultado de glob com caminho absoluto)

    else:
        working_dir = os.path.dirname(input_path)

        base_no_ext = os.path.splitext(os.path.basename(input_path))[0]
        is_rar_volume = input_path.endswith(".rar") and ".part" in base_no_ext

        if is_rar_volume:
            # Conjunto de volumes: inclui todos os partXX.rar do conjunto
            set_base = base_no_ext.rsplit(".part", 1)[0]
            vol_pattern = os.path.join(working_dir, glob.escape(set_base) + ".part*.rar")
            rar_volumes = sorted(glob.glob(vol_pattern))
            files_to_upload = (
                [os.path.basename(v) for v in rar_volumes]
                if rar_volumes
                else [os.path.basename(input_path)]
            )
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
        print(
            _("Erro: nenhum arquivo de paridade encontrado para '{path}'.").format(path=input_path)
        )
        print(_("Execute 'python3 makepar.py' primeiro para gerar os arquivos .par2"))
        return 3

    if obfuscated_map:
        random.shuffle(files_to_upload)
        random.shuffle(par2_files)

    # Carrega servidores NNTP (primário + opcionais failover)
    servers = _build_server_list(env_vars)
    if not servers or not servers[0]["host"]:
        print(_("Erro: NNTP_HOST não configurado."))
        return 2
    # Extrai credenciais do primário para validação e exibição
    nntp_host = servers[0]["host"]
    nntp_port = servers[0]["port"]
    nntp_user = servers[0]["user"]
    nntp_pass = servers[0]["password"]
    usenet_group = group or env_vars.get("USENET_GROUP") or os.environ.get("USENET_GROUP")

    # Pool de grupos: seleciona um grupo aleatório por upload para distribuir
    # o histórico entre múltiplos grupos e dificultar remoção seletiva.
    group_pool = []
    if usenet_group and "," in usenet_group:
        group_pool = [g.strip() for g in usenet_group.split(",") if g.strip()]
        if not obfuscated_map and group_pool:
            usenet_group = random.choice(group_pool)

    article_size = env_vars.get("ARTICLE_SIZE") or os.environ.get("ARTICLE_SIZE", "700K")
    if obfuscated_map:
        article_size = jitter_article_size(article_size)

    nzb_overwrite_env = env_vars.get("NZB_OVERWRITE") or os.environ.get("NZB_OVERWRITE")

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
        print(_("Erro: credenciais incompletas. Configure .env com:"))
        print(_("  NNTP_HOST=<seu_servidor>"))
        print(_("  NNTP_PORT=119"))
        print(_("  NNTP_USER=<seu_usuario>"))
        print(_("  NNTP_PASS=<sua_senha>"))
        print(_("  USENET_GROUP=<seu_grupo>"))
        return 2

    if len(servers) > 1:
        print(
            _("  Servidores NNTP:  {count} configurados (failover ativo)").format(
                count=len(servers)
            )
        )

    # Encontra nyuu
    if nyuu_path:
        if not os.path.exists(nyuu_path):
            print(_("Erro: nyuu não encontrado em '{path}'").format(path=nyuu_path))
            return 4
    else:
        nyuu_path = find_nyuu()
        if not nyuu_path:
            print(_("Erro: nyuu não encontrado. Instale-o (https://github.com/Piorosen/nyuu)"))
            return 4

    # Define subject
    if not subject:
        if is_folder:
            subject = os.path.basename(input_path)
        else:
            subject = os.path.basename(os.path.splitext(input_path)[0])

    # Geração de NFO para arquivo único (se não for pasta e tivermos caminho de NZB)
    # Isso garante que mesmo o upload direto via upfolder.py gere metadados.
    # Só roda em arquivos de mídia: .rar e outros contêineres não têm metadados úteis.
    _media_exts = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts"}
    if not is_folder and nzb_out_abs and os.path.splitext(input_path)[1].lower() in _media_exts:
        nfo_path = os.path.abspath(os.path.splitext(nzb_out_abs)[0] + ".nfo")
        if not os.path.exists(nfo_path):
            mediainfo_path = nfo.find_mediainfo()
            if mediainfo_path:
                try:
                    nfo_proc = subprocess.run(
                        [mediainfo_path, input_path], capture_output=True, text=True, check=True
                    )
                    with open(nfo_path, "w", encoding="utf-8") as nfo_fh:
                        nfo_fh.write(nfo_proc.stdout)
                except Exception:
                    pass

    # ── Lógica de resume (2.10) ──────────────────────────────────────────────
    # State file fica junto ao NZB de saída para fácil localização.
    state_path: str | None = nzb_out_abs + ".upapasta-state.json" if nzb_out_abs else None
    remaining_files = list(files_to_upload)
    remaining_par2 = list(par2_files)
    partial_nzb_backup: str | None = None  # caminho do NZB parcial salvo para merge

    if resume and nzb_out_abs and os.path.exists(nzb_out_abs):
        uploaded = _get_uploaded_files_from_nzb(nzb_out_abs)
        if uploaded:
            remaining_files = [f for f in files_to_upload if os.path.basename(f) not in uploaded]
            remaining_par2 = [p for p in par2_files if os.path.basename(p) not in uploaded]
            skipped = (
                len(files_to_upload) + len(par2_files) - len(remaining_files) - len(remaining_par2)
            )
            total_remaining = len(remaining_files) + len(remaining_par2)
            print(
                _("  ↩️  Resume: {skipped} arquivo(s) já postados, {remaining} restante(s)").format(
                    skipped=skipped, remaining=total_remaining
                )
            )
            if total_remaining == 0:
                print(_("  ✅ Todos os arquivos já foram postados. Upload completo."))
                return 0
            # Salva backup do NZB parcial; o novo upload vai escrever em nzb_out_abs
            partial_nzb_backup = nzb_out_abs + ".partial.nzb"
            try:
                import shutil as _shutil

                _shutil.copy2(nzb_out_abs, partial_nzb_backup)
            except Exception as e:
                print(_("Aviso: não foi possível salvar NZB parcial: {error}").format(error=e))
                partial_nzb_backup = None
        else:
            print(_("  Aviso: NZB existente está vazio. Reiniciando upload completo."))
    elif state_path and not resume and os.path.exists(state_path):
        print(
            _(
                "  Aviso: encontrado estado de upload anterior. Use --resume para retomar ou ignore para reiniciar."
            )
        )

    # ── Calcular tamanho total para exibição ─────────────────────────────────
    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.2f} MB"
        else:
            return f"{size_bytes / 1024**3:.2f} GB"

    total_size_bytes = 0
    for f in remaining_files:
        try:
            total_size_bytes += os.path.getsize(os.path.join(working_dir, f))
        except OSError:
            pass
    for f in remaining_par2:
        try:
            total_size_bytes += (
                os.path.getsize(f)
                if os.path.isabs(f)
                else os.path.getsize(os.path.join(working_dir, f))
            )
        except OSError:
            pass

    all_file_count = len(remaining_files) + len(remaining_par2)

    try:
        term_columns = shutil.get_terminal_size().columns
    except Exception:
        term_columns = 80
    sep = "─" * min(term_columns - 1, 60)

    rows = [
        (
            _("Host"),
            f"{nntp_host}:{nntp_port}"
            + (
                _(" + {count} failover(s)").format(count=len(servers) - 1)
                if len(servers) > 1
                else ""
            ),
        ),
        (_("Grupo"), usenet_group),
        (_("Subject"), subject),
        (
            _("Total"),
            _("{size}  ({count} arquivos)").format(
                size=format_size(total_size_bytes), count=all_file_count
            ),
        ),
    ]
    if nzb_out:
        rows.append((_("NZB"), nzb_out))

    if not bar:
        label_w = max(len(r[0]) for r in rows)
        print(sep)
        print(_("  Upload para Usenet"))
        print(sep)
        for label, value in rows:
            print(f"  {label:<{label_w}}  {value}")
        print(sep)
        print()

    # ── dry-run: monta cmd com servidor primário e imprime ────────────────────
    if dry_run:
        srv = servers[0]
        cmd_dry = [
            nyuu_path,
            "--progress",
            "stderrx",
            "-h",
            srv["host"],
            "-P",
            str(srv["port"]),
            *(["-S"] if srv.get("ssl") else []),
            *(["-i"] if srv.get("ignore_cert") else []),
            "-u",
            srv["user"],
            "-p",
            srv["password"],
            "-n",
            str(srv["connections"]),
            "-g",
            usenet_group,
            "-a",
            article_size,
            "-f",
            generate_anonymous_uploader(),
            "--date",
            "now",
            "-t",
            subject,
        ]
        if nzb_out_abs:
            cmd_dry.extend(["-o", nzb_out_abs])
        if nzb_overwrite:
            cmd_dry.append("-O")
        if upload_timeout is not None:
            cmd_dry.extend(["--timeout", str(upload_timeout)])
        if nyuu_extra_args:
            cmd_dry.extend(nyuu_extra_args)
        cmd_dry.extend(remaining_files)
        cmd_dry.extend(remaining_par2)
        print(_("Comando nyuu (dry-run):"))
        print(" ".join(str(x) for x in cmd_dry))
        return 0

    # ── Salvar estado antes de iniciar o upload ───────────────────────────────
    if state_path:
        _save_upload_state(state_path, files_to_upload, par2_files, working_dir, nzb_out_abs or "")

    if nzb_out_abs:
        os.makedirs(os.path.dirname(nzb_out_abs), exist_ok=True)

    # ── Configuração de Fragmentação Multigrupo ──────────────────────────────
    tmp_js_config = None
    if obfuscated_map and group_pool and len(group_pool) > 1:
        tmp_js_config = _create_nyuu_fragmentation_config(group_pool)

    try:
        # ── Executar nyuu com failover de servidor ────────────────────────────────
        # Em cada tentativa, rotaciona para o próximo servidor disponível.
        # Backoff exponencial: 30s → 90s → 270s com ±10% jitter.
        max_attempts = 1 + max(0, upload_retries)
        last_rc = 5
        _BACKOFF_BASE = 30

        # NZB de saída para esta rodada de upload
        nzb_target = nzb_out_abs

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                delay = _BACKOFF_BASE * (3 ** (attempt - 2))
                jitter = int(delay * 0.10 * (random.random() * 2 - 1))
                wait = max(1, delay + jitter)
                print(
                    _("\n⏳ Aguardando {wait}s antes da tentativa {attempt}/{max}...").format(
                        wait=wait, attempt=attempt, max=max_attempts
                    )
                )
                time.sleep(wait)

            srv = servers[(attempt - 1) % len(servers)]
            if len(servers) > 1:
                print(
                    _("\nTentativa {attempt}/{max} — servidor: {host}").format(
                        attempt=attempt, max=max_attempts, host=srv["host"]
                    )
                )
            elif attempt > 1:
                print(
                    _("\nTentativa {attempt}/{max} de upload...").format(
                        attempt=attempt, max=max_attempts
                    )
                )

            # Identidade: Schizo/Token-based se ofuscado, senão anônimo padrão.
            if obfuscated_map:
                # Token do nyuu para gerar poster aleatório POR ARTIGO
                # Formato: ${rand(8)}@${rand(5)}.com
                uploader = "${rand(8)}@${rand(5)}." + random.choice(["com", "net", "org"])
            else:
                uploader = generate_anonymous_uploader()

            cmd = [
                nyuu_path,
                "--progress",
                "stderrx",
                "-h",
                srv["host"],
                "-P",
                str(srv["port"]),
            ]
            if srv.get("ssl"):
                cmd.append("-S")
            if srv.get("ignore_cert"):
                cmd.append("-i")
            if obfuscated_map:
                cmd.append("--token-eval")
            if tmp_js_config:
                cmd.extend(["--config", tmp_js_config])

            cmd.extend(
                [
                    "-u",
                    srv["user"],
                    "-p",
                    srv["password"],
                    "-n",
                    str(srv["connections"]),
                    "-g",
                    usenet_group,  # Sempre inclui para que o NZB tenha todos os grupos no cabeçalho
                ]
            )
            cmd.extend(
                [
                    "-a",
                    article_size,
                    "-f",
                    uploader,
                    "--date",
                    "now",
                    "-t",
                    subject,
                ]
            )
            if nzb_target:
                cmd.extend(["-o", nzb_target])
            if nzb_overwrite or (resume and partial_nzb_backup):
                cmd.append("-O")
            if upload_timeout is not None:
                cmd.extend(["--timeout", str(upload_timeout)])
            if nyuu_extra_args:
                cmd.extend(nyuu_extra_args)
            # Arquivos a postar: restantes (resume) ou todos (upload normal)
            cmd.extend(remaining_files)
            cmd.extend(remaining_par2)

            try:
                with managed_popen(
                    cmd,
                    cwd=working_dir,
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
                    _process_output(output_queue, bar=bar)
                    last_rc = proc.wait()

                if last_rc == 0:
                    break
                print(
                    _("\nErro: nyuu retornou código {rc} no servidor {host}.").format(
                        rc=last_rc, host=srv["host"]
                    )
                )
            except KeyboardInterrupt:
                raise
            except FileNotFoundError:
                print(_("\nErro: nyuu não encontrado em '{path}'.").format(path=nyuu_path))
                return 4
            except OSError as e:
                print(_("\nErro de I/O ao executar nyuu: {error}").format(error=e))
                last_rc = 5

    finally:
        if tmp_js_config and os.path.exists(tmp_js_config):
            try:
                os.remove(tmp_js_config)
            except Exception:
                pass

    if last_rc != 0:
        return last_rc

    # ── Merge de NZBs em caso de resume ──────────────────────────────────────
    if partial_nzb_backup and nzb_out_abs and os.path.exists(nzb_out_abs):
        if merge_nzbs([partial_nzb_backup, nzb_out_abs], nzb_out_abs):
            os.remove(partial_nzb_backup)
            print(_("  ↩️  NZBs parciais mesclados com sucesso."))
        else:
            print(
                _("  Aviso: falha ao mesclar NZBs. NZB parcial original em '{path}'.").format(
                    path=partial_nzb_backup
                )
            )

    # ── Remover state file após upload completo ───────────────────────────────
    if state_path and os.path.exists(state_path):
        try:
            os.remove(state_path)
        except Exception:
            pass

    # ── Pós-processamento do NZB ─────────────────────────────────────────────
    if nzb_out_abs and os.path.exists(nzb_out_abs) and (is_folder or obfuscated_map or folder_name):
        par2_basenames = [os.path.basename(f) for f in par2_files]
        all_files = files_to_upload + par2_basenames

        # Calcula tamanhos em bytes de cada arquivo para matching por segmentos no NZB.
        # O nyuu não preserva a ordem de upload no NZB, portanto não se pode usar
        # índice — o match por tamanho é o único método confiável.
        _art_bytes = _article_size_to_bytes(article_size)
        _file_sizes: dict[str, int] = {}
        for f in files_to_upload:
            fp = os.path.join(working_dir, f)
            try:
                _file_sizes[f] = os.path.getsize(fp)
            except OSError:
                pass
        for abs_path, basename in zip(par2_files, par2_basenames):
            try:
                _file_sizes[basename] = os.path.getsize(abs_path)
            except OSError:
                pass

        fix_nzb_subjects(
            nzb_out_abs,
            all_files,
            folder_name,
            obfuscated_map,
            file_sizes=_file_sizes,
            article_size_bytes=_art_bytes,
        )

    if nzb_out_abs and os.path.exists(nzb_out_abs) and password and not skip_rar:
        inject_nzb_password(nzb_out_abs, password)
        if bar:
            bar.log(_("Senha injetada no NZB."))
        else:
            print(_("Senha injetada no NZB."))

    if nzb_out_abs:
        if not _verify_nzb(nzb_out_abs):
            msg = _("Aviso: NZB gerado em '{path}' está ausente, vazio ou inválido.").format(
                path=nzb_out_abs
            )
            if bar:
                bar.log(msg)
            else:
                print(msg)
        else:
            msg = _("NZB verificado: {name}").format(name=os.path.basename(nzb_out_abs))
            if bar:
                bar.log(msg)
            else:
                print(msg)

    return 0
