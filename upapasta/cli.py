"""
cli.py

Definição de interface de linha de comando (CLI) e verificação de dependências.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import DEFAULT_ENV_FILE


_USAGE_SHORT = """\
UpaPasta — uploader automatizado para Usenet

  Uso:  upapasta <caminho>  [opções]

  Exemplos rápidos:
    upapasta Filme.2024/ --rar            pasta inteira como um release (RAR + PAR2)
    upapasta Episodio.S01E01.mkv          arquivo único sem RAR
    upapasta Temporada.1/ --each          cada arquivo da pasta vira um release separado
    upapasta Pasta/ --obfuscate           release com nomes ofuscados
    upapasta Pasta/ --password abc --rar  release com senha no RAR
    upapasta Pasta/ --dry-run             simula sem enviar nada

  Para ajuda completa:  upapasta --help
"""

_DESCRIPTION = "UpaPasta — uploader automatizado para Usenet"

_EPILOG = """\
COMPORTAMENTO PADRÃO
  Pasta   → PAR2 (balanced) + upload direto (sem RAR) → NZB + NFO
  Arquivo → PAR2 + upload direto (sem RAR) → NZB + NFO
  Com --rar: cria RAR primeiro, depois PAR2 + upload

  --obfuscate: nomes aleatórios (sem RAR por padrão; proteção via parpar + ofuscação).
  --obfuscate --password abc: nomes aleatórios + RAR com senha.
  --password sozinho: presume --rar automaticamente (precisa de RAR para proteger).
  Arquivo único com --obfuscate ou --password: cria RAR automaticamente.

FLUXO RECOMENDADO 2026 (padrão moderno)
  upapasta Pasta/ --obfuscate --backend parpar \\
      --filepath-format common --par-profile safe

  Por quê: parpar grava a estrutura de pastas nos .par2; SABnzbd/NZBGet
  recentes reconstroem a árvore no download. RAR é opcional — ofuscação
  forte + PAR2 já protege contra scans automáticos de copyright. Use --rar
  apenas se precisar do RAR-com-senha (casos legados).

  No SABnzbd: desative "Recursive Unpacking" e revise "Unwanted Extensions".
  Use --rename-extensionless se houver arquivos sem extensão (evita .txt do SAB).

EXEMPLOS
  upapasta Pasta/ --obfuscate                 fluxo moderno (recomendado)
  upapasta Filme.2024/ --rar                  pasta como release único (com RAR)
  upapasta Episodio.S01E01.mkv               arquivo único, sem RAR
  upapasta Temporada.1/ --each               cada arquivo da pasta separado
  upapasta Pasta/ --password "abc123"         RAR com senha (presume --rar automaticamente)
  upapasta Pasta/ --filepath-format keep     preserva caminho completo
"""


def parse_args():
    p = argparse.ArgumentParser(
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Arquivo ou pasta a fazer upload",
    )
    p.add_argument(
        "--config",
        action="store_true",
        help="Abre o wizard de configuração (permite reconfigurar credenciais e opções)",
    )
    p.add_argument(
        "--test-connection",
        action="store_true",
        help="Testa conectividade com o servidor NNTP (valida host, porta e credenciais)",
    )
    # ── Opções essenciais ────────────────────────────────────────────────────
    essential = p.add_argument_group("opções essenciais")
    essential.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Usa um perfil de configuração nomeado (~/.config/upapasta/<profile>.env)",
    )
    essential.add_argument(
        "--watch",
        action="store_true",
        help=(
            "Modo daemon: monitora <input> continuamente e processa novos itens automaticamente. "
            "Incompatível com --each/--season. Ctrl+C encerra."
        ),
    )
    essential.add_argument(
        "--each",
        action="store_true",
        help=(
            "Processa cada arquivo da pasta individualmente. "
            "Ideal para temporadas: cada episódio vira um release separado com seu próprio NZB."
        ),
    )
    essential.add_argument(
        "--season",
        action="store_true",
        help=(
            "Similar ao --each: upload individual de cada episódio, mas ao final "
            "gera um NZB único contendo toda a temporada, além dos NZBs individuais."
        ),
    )
    essential.add_argument(
        "--obfuscate",
        action="store_true",
        help=(
            "Release privado: nomes aleatórios no RAR/PAR2 + senha gerada automaticamente. "
            "Em arquivo único, cria RAR automaticamente. "
            "Use --password junto para definir a senha manualmente."
        ),
    )
    essential.add_argument(
        "--password",
        default=None,
        metavar="SENHA",
        help=(
            "Senha para o RAR (injetada no NZB para extração automática por SABnzbd/NZBGet). "
            "Presume automaticamente --rar (precisa de RAR para proteger com senha)."
        ),
    )
    essential.add_argument(
        "--rar",
        action="store_true",
        help="Cria RAR antes do upload. Padrão é desativado (enviar arquivos como estão com PAR2).",
    )
    essential.add_argument(
        "--skip-rar",
        action="store_true",
        dest="skip_rar_deprecated",
        help="[DEPRECATED: use ausência de --rar] Não cria RAR.",
    )
    essential.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula todo o processo sem criar ou enviar arquivos.",
    )

    # ── Opções de ajuste ─────────────────────────────────────────────────────
    tuning = p.add_argument_group("opções de ajuste")
    tuning.add_argument(
        "--par-profile",
        choices=("fast", "balanced", "safe"),
        default="balanced",
        help="Perfil PAR2: fast=5%%, balanced=10%% (padrão), safe=20%%",
    )
    tuning.add_argument(
        "-r", "--redundancy",
        type=int,
        default=None,
        metavar="PERCENT",
        help="Redundância PAR2 em %% (sobrescreve --par-profile)",
    )
    tuning.add_argument(
        "--keep-files",
        action="store_true",
        help="Mantém RAR e PAR2 após o upload",
    )
    tuning.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Grava log completo da sessão em arquivo",
    )
    tuning.add_argument(
        "--upload-retries",
        type=int,
        default=0,
        metavar="N",
        help="Tentativas extras de upload em caso de falha (padrão: 0)",
    )
    tuning.add_argument(
        "--verbose",
        action="store_true",
        help="Ativa log de debug detalhado",
    )
    tuning.add_argument(
        "--watch-interval",
        type=int,
        default=30,
        metavar="N",
        help="Intervalo de varredura do --watch em segundos (padrão: 30)",
    )
    tuning.add_argument(
        "--watch-stable",
        type=int,
        default=60,
        metavar="N",
        help="Segundos que o tamanho deve ser estável antes de processar (padrão: 60)",
    )

    # ── Opções avançadas ─────────────────────────────────────────────────────
    advanced = p.add_argument_group("opções avançadas")
    advanced.add_argument(
        "--backend",
        choices=("parpar", "par2"),
        default="parpar",
        help="Backend PAR2: parpar (padrão) ou par2",
    )
    advanced.add_argument(
        "--post-size",
        default=None,
        metavar="SIZE",
        help="Tamanho alvo de post (ex: 20M, 700K — sobrescreve perfil)",
    )
    advanced.add_argument(
        "--par-slice-size",
        default=None,
        metavar="SIZE",
        help="Override manual do slice PAR2 (ex: 512K, 1M, 2M)",
    )
    advanced.add_argument(
        "--rar-threads",
        type=int,
        default=None,
        metavar="N",
        help="Threads para RAR (padrão: CPUs disponíveis)",
    )
    advanced.add_argument(
        "--par-threads",
        type=int,
        default=None,
        metavar="N",
        help="Threads para PAR2 (padrão: CPUs disponíveis)",
    )
    advanced.add_argument(
        "--max-memory",
        type=int,
        default=None,
        metavar="MB",
        help="Limite de memória para PAR2 em MB (padrão: automático)",
    )
    advanced.add_argument(
        "-s", "--subject",
        default=None,
        help="Assunto da postagem (padrão: nome do arquivo/pasta)",
    )
    advanced.add_argument(
        "-g", "--group",
        default=None,
        help="Newsgroup (padrão: do .env)",
    )
    advanced.add_argument(
        "--nzb-conflict",
        choices=("rename", "overwrite", "fail"),
        default=None,
        help="Comportamento quando .nzb já existe: rename (padrão), overwrite, fail",
    )
    advanced.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        metavar="PATH",
        help="Caminho alternativo para o .env (padrão: ~/.config/upapasta/.env)",
    )
    advanced.add_argument(
        "--upload-timeout",
        type=int,
        default=None,
        metavar="N",
        help="Timeout de conexão para nyuu em segundos",
    )
    advanced.add_argument(
        "-f", "--force",
        action="store_true",
        help="Sobrescreve RAR/PAR2 existentes",
    )
    advanced.add_argument(
        "--skip-par",
        action="store_true",
        help="Pula geração de paridade",
    )
    advanced.add_argument(
        "--skip-upload",
        action="store_true",
        help="Pula upload para Usenet",
    )
    advanced.add_argument(
        "--filepath-format",
        choices=("common", "keep", "basename", "outrel"),
        default="common",
        help=(
            "Como o parpar grava paths nos .par2 (default: common). "
            "common=descarta prefixo comum (preserva subpastas relativas); "
            "keep=preserva o caminho completo; basename=descarta paths (flat); "
            "outrel=relativo à saída. Ignorado quando backend=par2."
        ),
    )
    advanced.add_argument(
        "--parpar-args",
        default=None,
        metavar="STR",
        help=(
            "Args extras repassados ao parpar, ex: --parpar-args \"--noindex --foo=bar\". "
            "Tokenizado via shlex. Ignorado quando backend=par2."
        ),
    )
    advanced.add_argument(
        "--nyuu-args",
        default=None,
        metavar="STR",
        help=(
            "Args extras repassados ao nyuu, ex: --nyuu-args \"--article-threads=8 --queue=20\". "
            "Tokenizado via shlex."
        ),
    )
    advanced.add_argument(
        "--rename-extensionless",
        action="store_true",
        help=(
            "Renomeia arquivos sem extensão para .bin antes do upload (reverte ao final). "
            "Evita que o SABnzbd adicione .txt em arquivos sem extensão."
        ),
    )

    return p.parse_args()


def check_dependencies(rar_needed: bool = True) -> bool:
    """Verifica se os binários necessários estão no PATH."""
    required_commands = ["nyuu", "parpar"]
    if rar_needed:
        required_commands.append("rar")

    missing_commands = []
    for cmd in required_commands:
        if not shutil.which(cmd):
            missing_commands.append(cmd)

    if missing_commands:
        print("❌ Dependências não encontradas:")
        for cmd in missing_commands:
            print(f"  - '{cmd}' não está instalado ou não está no PATH.")
        print("\n   Por favor, instale as dependências e tente novamente.")
        print("   Você pode encontrar instruções de instalação em INSTALL.md")
        return False

    # Verificação de dependências opcionais (para NFO)
    optional_commands = ["mediainfo", "ffprobe"]
    missing_optional = [cmd for cmd in optional_commands if not shutil.which(cmd)]
    if missing_optional:
        print(f"⚠️  Dependências opcionais ausentes: {', '.join(missing_optional)}")
        print("   A geração de arquivos .nfo será limitada ou ignorada.")
    else:
        print("✅ Todas as dependências (incluindo opcionais) foram encontradas.")

    return True


def _validate_flags(args) -> bool:
    """Valida combinações de flags incompatíveis. Retorna False se há erro fatal."""
    # Backward compatibility: --skip-rar → sem --rar
    if getattr(args, 'skip_rar_deprecated', False):
        print("⚠️  --skip-rar está deprecado. O padrão já é sem RAR.")
        print("   Para usar RAR, adicione --rar explicitamente.")
        # Ignora --skip-rar deprecated e mantém --rar = False
        args.rar = False

    # --password presume --rar (precisa de RAR para proteger com senha)
    if args.password and not args.rar:
        print("ℹ️  --password ativa --rar automaticamente (precisa de RAR para proteger).")
        args.rar = True

    if args.each or args.season:
        p = Path(args.input)
        if not p.is_dir():
            mode = "--each" if args.each else "--season"
            print(f"❌  {mode} requer uma pasta como entrada.")
            return False

    if args.watch:
        if not args.input or not Path(args.input).is_dir():
            print("❌  --watch requer uma pasta como entrada.")
            return False
        if args.each or args.season:
            print("❌  --watch é incompatível com --each e --season.")
            return False

    if args.obfuscate and not args.rar:
        # Em 2026 esse fluxo é o recomendado: ofuscação externa nos nomes que
        # vão para os headers NNTP + paths preservados dentro dos .par2 pelo
        # parpar (filepath-format). Não há ofuscação "parcial" — a estrutura
        # interna fica protegida pelo próprio mecanismo do parpar.
        print(
            "✅ Fluxo moderno: --obfuscate (sem RAR).\n"
            "   Nomes externos ofuscados; estrutura preservada via parpar."
        )

    return True
