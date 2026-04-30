"""
config.py

Configurações centralizadas: perfis PAR2, credenciais e defaults.
"""

from __future__ import annotations

import getpass
import os

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


def _ask(prompt: str, default: str = None, validator=None, secret: bool = False) -> str:
    hint = f" [{default}]" if default is not None else ""
    while True:
        if secret:
            val = getpass.getpass(f"  {prompt}{hint}: ")
        else:
            val = input(f"  {prompt}{hint}: ").strip()
        if val == "" and default is not None:
            val = default
        if not val:
            print("    Valor obrigatório. Tente novamente.")
            continue
        if validator and not validator(val):
            continue
        return val


def _is_numeric_port(val: str) -> bool:
    if not val.isdigit() or not (1 <= int(val) <= 65535):
        print("    Porta inválida. Use um número entre 1 e 65535.")
        return False
    return True


def render_template(template: str, filename: str) -> str:
    """Renderiza um template substituindo {filename} pelo valor fornecido."""
    return template.replace("{filename}", filename)


def _write_full_env(env_file: str, values: dict) -> None:
    # Preserva valores que já existem no .env mas não foram respondidos no wizard
    existing = load_env_file(env_file) if os.path.exists(env_file) else {}
    merged = {**existing, **values}

    def v(key: str) -> str:
        return merged.get(key, "")

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

PROFILES = {
    "fast": {
        "description": "Máxima velocidade (ideal para upload urgente)",
        "slice_size": "20M",
        "redundancy": 5,
        "post_size": "100M",
    },
    "balanced": {
        # slice_size=None → makepar.py calcula dinamicamente via ARTICLE_SIZE do .env
        "description": "Equilibrado (RECOMENDADO para Usenet) — slice dinâmico automático",
        "slice_size": None,
        "redundancy": 10,
        "post_size": "50M",
    },
    "safe": {
        "description": "Alta proteção (ideal para arquivos críticos)",
        "slice_size": "5M",
        "redundancy": 20,
        "post_size": "30M",
    },
}

DEFAULT_PROFILE = "balanced"


def load_env_file(env_path: str = DEFAULT_ENV_FILE) -> dict:
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


def prompt_for_credentials(env_file: str, force: bool = False) -> dict:
    """Solicita credenciais ao usuário e salva um .env completo com todos os campos."""
    existing = load_env_file(env_file) if (force and os.path.exists(env_file)) else {}

    def ex(key: str, fallback: str) -> str:
        return existing.get(key) or fallback

    def ex_secret(key: str) -> str:
        """Retorna '****' se já existe valor, senão None (obriga preenchimento)."""
        return "****" if existing.get(key) else None

    print()
    if force and existing:
        print("╔══════════════════════════════════════════════════════╗")
        print("║         Reconfiguração do UpaPasta                   ║")
        print("║  Pressione Enter para manter o valor atual           ║")
        print("╚══════════════════════════════════════════════════════╝")
    else:
        print("╔══════════════════════════════════════════════════════╗")
        print("║         Configuração inicial do UpaPasta             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()
        print("Credenciais do servidor NNTP não encontradas.")
    print(f"Arquivo de configuração: {env_file}")
    print()

    print("── Servidor NNTP ─────────────────────────────────────")
    host = _ask("Servidor NNTP (ex: news.eweka.nl)", default=ex("NNTP_HOST", None), validator=lambda v: (True if v and " " not in v else (print("    Endereço inválido.") or False)))
    port = _ask("Porta NNTP", default=ex("NNTP_PORT", "563"), validator=_is_numeric_port)
    ssl  = _ask("Usar SSL/TLS?", default=ex("NNTP_SSL", "true"), validator=lambda v: (True if v.lower() in ("true", "false") else (print("    Digite true ou false.") or False)))
    user = _ask("Usuário NNTP", default=ex("NNTP_USER", None))

    # Senha: se já existe, permite manter com Enter
    passwd_hint = ex_secret("NNTP_PASS")
    if passwd_hint:
        raw = getpass.getpass(f"  Senha NNTP [****]: ")
        passwd = raw if raw.strip() else existing["NNTP_PASS"]
    else:
        passwd = _ask("Senha NNTP", secret=True)

    print()
    print("── Upload ────────────────────────────────────────────")
    print("  Dica: Você pode fornecer um único grupo ou uma lista separada por vírgulas.")
    print("  Se fornecer uma lista, o UpaPasta sorteará um grupo aleatório por upload.")
    group       = _ask("Grupo Usenet (ou Pool)", default=ex("USENET_GROUP", DEFAULT_GROUP_POOL))
    connections = _ask("Conexões simultâneas (verifique o limite do seu plano)", default=ex("NNTP_CONNECTIONS", "50"))
    article_sz  = _ask("Tamanho do artigo", default=ex("ARTICLE_SIZE", "700K"))
    nzb_out     = _ask("Caminho de saída do .nzb ({filename} = nome do upload)", default=ex("NZB_OUT", "{filename}.nzb"))
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
    print("── Resumo ────────────────────────────────────────────")
    print(f"  Servidor  : {host}:{port}  SSL={ssl.lower()}")
    print(f"  Usuário   : {user}")
    print(f"  Grupo     : {group}")
    print(f"  Conexões  : {connections}  Artigo: {article_sz}")
    print(f"  NZB out   : {nzb_out}")
    print()

    _write_full_env(env_file, values)
    print(f"✅ Configuração salva em '{env_file}'.")
    print("   Edite esse arquivo a qualquer momento para ajustar as opções.")
    print()
    return values


def check_or_prompt_credentials(env_file: str, force: bool = False) -> dict:
    """Verifica se as credenciais existem e estão preenchidas, senão, solicita."""
    if force:
        return prompt_for_credentials(env_file, force=True)

    env_vars = load_env_file(env_file)

    missing_or_empty = [k for k in REQUIRED_CRED_KEYS if not env_vars.get(k)]
    is_default_host = env_vars.get("NNTP_HOST") == "news.example.com"
    is_default_user = env_vars.get("NNTP_USER") == "seu_usuario"

    if missing_or_empty or is_default_host or is_default_user:
        return prompt_for_credentials(env_file)

    print("✅ Credenciais de Usenet carregadas.")
    return env_vars
