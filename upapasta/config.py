"""
config.py

Configurações centralizadas: perfis PAR2, credenciais e defaults.
"""

import getpass
import os

DEFAULT_ENV_FILE = os.path.expanduser("~/.config/upapasta/.env")

REQUIRED_CRED_KEYS = ["NNTP_HOST", "NNTP_PORT", "NNTP_USER", "NNTP_PASS", "USENET_GROUP"]

PROFILES = {
    "fast": {
        "description": "Máxima velocidade (ideal para upload urgente)",
        "slice_size": "20M",
        "redundancy": 5,
        "post_size": "100M",
    },
    "balanced": {
        "description": "Equilibrado (RECOMENDADO para Usenet)",
        "slice_size": "10M",
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


def prompt_for_credentials(env_file: str) -> dict:
    """Solicita credenciais ao usuário e salva no arquivo .env."""
    print("🔑 Credenciais de Usenet não encontradas ou incompletas.")
    print("Por favor, forneça as seguintes informações:")

    creds = {
        "NNTP_HOST": input("   - Servidor NNTP (ex: news.example.com): "),
        "NNTP_PORT": input("   - Porta NNTP (ex: 563): "),
        "NNTP_USER": input("   - Usuário NNTP: "),
        "NNTP_PASS": getpass.getpass("   - Senha NNTP: "),
        "USENET_GROUP": input("   - Grupo Usenet (ex: alt.binaries.test): "),
    }

    creds["NNTP_SSL"] = "true"
    creds["NNTP_CONNECTIONS"] = "50"
    creds["ARTICLE_SIZE"] = "700K"

    os.makedirs(os.path.dirname(env_file), exist_ok=True)

    with open(env_file, "w") as f:
        f.write("# Configuração de credenciais para upload em Usenet com nyuu\n")
        for key, value in creds.items():
            f.write(f"{key}={value}\n")

    print(f"\n✅ Credenciais salvas em '{env_file}'.")
    return creds


def check_or_prompt_credentials(env_file: str) -> dict:
    """Verifica se as credenciais existem e estão preenchidas, senão, solicita."""
    env_vars = load_env_file(env_file)

    missing_or_empty = [k for k in REQUIRED_CRED_KEYS if not env_vars.get(k)]
    is_default_host = env_vars.get("NNTP_HOST") == "news.example.com"
    is_default_user = env_vars.get("NNTP_USER") == "seu_usuario"

    if missing_or_empty or is_default_host or is_default_user:
        return prompt_for_credentials(env_file)

    print("✅ Credenciais de Usenet carregadas.")
    return env_vars
