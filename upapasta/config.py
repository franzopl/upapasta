"""
config.py

Configurações centralizadas: perfis PAR2, credenciais e defaults.
"""

from __future__ import annotations

import getpass
import os
from typing import Callable, Optional

from .i18n import _
from .profiles import DEFAULT_PROFILE, PROFILES  # noqa: E402

CONFIG_DIR = os.path.expanduser("~/.config/upapasta")
DEFAULT_ENV_FILE = os.path.join(CONFIG_DIR, ".env")

REQUIRED_CRED_KEYS = ["NNTP_HOST", "NNTP_PORT", "NNTP_USER", "NNTP_PASS", "USENET_GROUP"]


def resolve_env_file(profile: str | None = None) -> str:
    """Resolve o caminho do arquivo .env baseado no perfil.

    Se profile for None, retorna o arquivo .env padrão.
    Se profile for especificado, retorna ~/.config/upapasta/<profile>.env
    """
    if profile is None:
        return DEFAULT_ENV_FILE
    return os.path.join(CONFIG_DIR, f"{profile}.env")

# Pool de grupos populares para aumentar obfuscação e redundância
DEFAULT_GROUP_POOL = (
    "alt.binaries.boneless,"
    "alt.binaries.mom,"
    "alt.binaries.etc,"
    "alt.binaries.u4e,"
    "alt.binaries.moovee,"
    "alt.binaries.teevee,"
    "alt.binaries.hdtv,"
    "alt.binaries.misc,"
    "alt.binaries.inner-earth,"
    "alt.binaries.multimedia"
)


def _ask(prompt: str, default: str | None = None, validator: Optional[Callable[[str], bool]] = None, secret: bool = False) -> str:
    hint = f" [{default}]" if default is not None else ""
    while True:
        if secret:
            val = getpass.getpass(_("  {prompt}{hint}: ").format(prompt=prompt, hint=hint))
        else:
            val = input(_("  {prompt}{hint}: ").format(prompt=prompt, hint=hint)).strip()
        if val == "" and default is not None:
            val = default
        if not val:
            print(_("    Required value. Try again."))
            continue
        if validator and not validator(val):
            continue
        return val


def _is_numeric_port(val: str) -> bool:
    if not val.isdigit() or not (1 <= int(val) <= 65535):
        print(_("    Invalid port. Use a number between 1 and 65535."))
        return False
    return True


def render_template(template: str, filename: str) -> str:
    """Renderiza um template substituindo {filename} pelo valor fornecido."""
    return template.replace("{filename}", filename)


def _write_full_env(env_file: str, values: dict[str, str]) -> None:
    # Preserva valores que já existem no .env mas não foram respondidos no wizard
    existing = load_env_file(env_file) if os.path.exists(env_file) else {}
    merged = {**existing, **values}

    def v(key: str) -> str:
        val = merged.get(key, "")
        return val if isinstance(val, str) else ""

    lines = [
        "# Configuração para upload em Usenet com nyuu",
        "# Edite este arquivo para ajustar qualquer opção.",
        "",
        "# *** Server Options ***",
        "# Servidor NNTP do seu provedor (ex: news.eweka.nl, news.usenetexpress.com)",
        f"NNTP_HOST={v('NNTP_HOST')}",
        "",
        "# Porta NNTP (119 = sem criptografia, 443/563 = TLS/SSL)",
        f"NNTP_PORT={v('NNTP_PORT')}",
        "",
        "# Usar SSL/TLS (true/false)",
        f"NNTP_SSL={v('NNTP_SSL')}",
        "",
        "# Ignorar erro de certificado SSL (true/false) — use apenas se necessário",
        f"NNTP_IGNORE_CERT={v('NNTP_IGNORE_CERT')}",
        "",
        "# Usuário NNTP fornecido pelo seu provedor",
        f"NNTP_USER={v('NNTP_USER')}",
        "",
        "# Senha NNTP",
        f"NNTP_PASS={v('NNTP_PASS')}",
        "",
        "# Número de conexões simultâneas (verifique o limite do seu plano)",
        f"NNTP_CONNECTIONS={v('NNTP_CONNECTIONS')}",
        "",
        "# *** Article Options ***",
        "# Grupo Usenet para upload (alt.binaries.boneless é amplamente retido)",
        f"USENET_GROUP={v('USENET_GROUP')}",
        "",
        "# Tamanho máximo de cada artigo (700K é o padrão mais compatível)",
        f"ARTICLE_SIZE={v('ARTICLE_SIZE')}",
        "",
        "# *** Check Options ***",
        "# Conexões usadas para verificar se os posts chegaram ao servidor",
        f"CHECK_CONNECTIONS={v('CHECK_CONNECTIONS')}",
        "",
        "# Quantas vezes tentar verificar cada artigo",
        f"CHECK_TRIES={v('CHECK_TRIES')}",
        "",
        "# Intervalo entre tentativas de verificação (ex: 5s, 30s)",
        f"CHECK_DELAY={v('CHECK_DELAY')}",
        "",
        "# Delay antes de um retry de verificação após falha",
        f"CHECK_RETRY_DELAY={v('CHECK_RETRY_DELAY')}",
        "",
        "# Tentativas de verificação por post",
        f"CHECK_POST_TRIES={v('CHECK_POST_TRIES')}",
        "",
        "# *** NZB Options ***",
        "# Caminho de saída do arquivo .nzb ({filename} = nome do arquivo enviado)",
        f"NZB_OUT={v('NZB_OUT')}",
        "",
        "# Sobrescrever .nzb existente com mesmo nome (true/false)",
        f"NZB_OVERWRITE={v('NZB_OVERWRITE')}",
        "",
        "# *** Other Options ***",
        "# Ignorar erros de upload (all = ignora tudo, none = aborta ao primeiro erro)",
        f"SKIP_ERRORS={v('SKIP_ERRORS')}",
        "",
        "# Pasta para salvar posts que falharam (deixe vazio para desativar)",
        f"DUMP_FAILED_POSTS={v('DUMP_FAILED_POSTS')}",
        "",
        "# Args extras repassados ao nyuu (ex: --article-threads=8 --queue=20)",
        f"NYUU_EXTRA_ARGS={v('NYUU_EXTRA_ARGS')}",
        "",
        "# Modo silencioso: suprime saída do nyuu (true/false)",
        f"QUIET={v('QUIET')}",
        "",
        "# *** UI Options ***",
        "# Exibir timestamp nos logs (true/false)",
        f"LOG_TIME={v('LOG_TIME')}",
        "",
    ]

    os.makedirs(os.path.dirname(env_file), exist_ok=True)
    with open(env_file, "w") as f:
        f.write("\n".join(lines))

__all__ = ["DEFAULT_PROFILE", "PROFILES"]


def load_env_file(env_path: str = DEFAULT_ENV_FILE) -> dict[str, str]:
    """Carrega variáveis de ambiente de um arquivo .env simples."""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        env_vars[key.strip()] = val.strip()
    return env_vars


def prompt_for_credentials(env_file: str, force: bool = False) -> dict[str, str]:
    """Solicita credenciais ao usuário e salva um .env completo com todos os campos."""
    existing = load_env_file(env_file) if (force and os.path.exists(env_file)) else {}

    def ex(key: str, fallback: str | None) -> str | None:
        return existing.get(key) or fallback

    def ex_secret(key: str) -> str | None:
        """Retorna '****' se já existe valor, senão None (obriga preenchimento)."""
        return "****" if existing.get(key) else None

    print()
    if force and existing:
        print("╔══════════════════════════════════════════════════════╗")
        print(_("║         UpaPasta Reconfiguration                     ║"))
        print(_("║  Press Enter to keep current value                   ║"))
        print("╚══════════════════════════════════════════════════════╝")
    else:
        print("╔══════════════════════════════════════════════════════╗")
        print(_("║         UpaPasta Initial Setup                       ║"))
        print("╚══════════════════════════════════════════════════════╝")
        print()
        print(_("NNTP server credentials not found."))
    print(_("Configuration file: {path}").format(path=env_file))
    print()

    print(_("── NNTP Server ───────────────────────────────────────"))
    host = _ask(_("NNTP Server (ex: news.eweka.nl)"), default=ex("NNTP_HOST", None) or "", validator=lambda v: (True if v and " " not in v else (print(_("    Invalid address.")) or False)))
    port = _ask(_("NNTP Port"), default=ex("NNTP_PORT", "563") or "563", validator=_is_numeric_port)
    ssl  = _ask(_("Use SSL/TLS?"), default=ex("NNTP_SSL", "true") or "true", validator=lambda v: (True if v.lower() in ("true", "false") else (print(_("    Type true or false.")) or False)))
    user = _ask(_("NNTP User"), default=ex("NNTP_USER", None) or "")

    # Senha: se já existe, permite manter com Enter
    passwd_hint = ex_secret("NNTP_PASS")
    if passwd_hint:
        raw = getpass.getpass(_("  NNTP Password [****]: "))
        passwd = raw if raw.strip() else existing["NNTP_PASS"]
    else:
        passwd = _ask(_("NNTP Password"), secret=True)

    print()
    print(_("── Upload ────────────────────────────────────────────"))
    print(_("  Hint: You can provide a single group or a comma-separated list."))
    print(_("  If a list is provided, UpaPasta will pick a random group per upload."))
    group       = _ask(_("Usenet Group (or Pool)"), default=ex("USENET_GROUP", DEFAULT_GROUP_POOL))
    connections = _ask(_("Simultaneous connections (check your plan limit)"), default=ex("NNTP_CONNECTIONS", "50"))
    article_sz  = _ask(_("Article size"), default=ex("ARTICLE_SIZE", "700K"))
    nzb_out     = _ask(_("Output path for .nzb ({{filename}} = upload name)"), default=ex("NZB_OUT", "{filename}.nzb"))
    # Se o usuário indicou apenas uma pasta (não contém {filename} e não termina em .nzb)
    if "{filename}" not in nzb_out and not nzb_out.lower().endswith(".nzb"):
        nzb_out = os.path.join(nzb_out, "{filename}.nzb")

    values = {
        "NNTP_HOST":           host,
        "NNTP_PORT":           port,
        "NNTP_SSL":            ssl.lower(),
        "NNTP_IGNORE_CERT":    "false",
        "NNTP_USER":           user,
        "NNTP_PASS":           passwd,
        "NNTP_CONNECTIONS":    connections,
        "USENET_GROUP":        group,
        "ARTICLE_SIZE":        article_sz,
        "CHECK_CONNECTIONS":   "5",
        "CHECK_TRIES":         "2",
        "CHECK_DELAY":         "5s",
        "CHECK_RETRY_DELAY":   "30s",
        "CHECK_POST_TRIES":    "2",
        "NZB_OUT":             nzb_out,
        "NZB_OVERWRITE":       "true",
        "SKIP_ERRORS":         "all",
        "DUMP_FAILED_POSTS":   "",
        "QUIET":               "false",
        "LOG_TIME":            "true",
    }

    print()
    print(_("── Summary ───────────────────────────────────────────"))
    print(_("  Server    : {host}").format(host=host))
    print(_("  User      : {user}").format(user=user))
    print(_("  Group     : {group}").format(group=group))
    print(_("  Conns     : {connections}  Article: {size}").format(connections=connections, size=article_sz))
    print(_("  NZB out   : {nzb}").format(nzb=nzb_out))
    print()

    _write_full_env(env_file, values)
    print(_("✅ Configuration saved to '{path}'.").format(path=env_file))
    print(_("   Edit this file at any time to adjust settings."))
    print()
    return values


def check_or_prompt_credentials(env_file: str, force: bool = False) -> dict[str, str]:
    """Verifica se as credenciais existem e estão preenchidas, senão, solicita."""
    if force:
        return prompt_for_credentials(env_file, force=True)

    env_vars = load_env_file(env_file)

    missing_or_empty = [k for k in REQUIRED_CRED_KEYS if not env_vars.get(k)]
    is_default_host = env_vars.get("NNTP_HOST") == "news.example.com"
    is_default_user = env_vars.get("NNTP_USER") == "seu_usuario"

    if missing_or_empty or is_default_host or is_default_user:
        return prompt_for_credentials(env_file)

    print(_("✅ Usenet credentials loaded."))
    return env_vars
