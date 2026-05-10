"""
cli.py

Definição de interface de linha de comando (CLI) e verificação de dependências.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .config import DEFAULT_ENV_FILE
from .i18n import _

_USAGE_SHORT = _("""\
UpaPasta — uploader automatizado para Usenet

  Uso:  upapasta <caminho> [<caminho2> ...]  [opções]

  Exemplos rápidos:
    upapasta Filme.2024/ --rar              pasta inteira como um release (RAR + PAR2)
    upapasta Episodio.S01E01.mkv            arquivo único sem RAR
    upapasta A.mkv B.mkv C.mkv             múltiplos arquivos em sequência
    upapasta Pasta1/ Pasta2/ --jobs 2      duas pastas em paralelo
    upapasta Temporada.1/ --each           cada arquivo da pasta vira um release separado
    upapasta Pasta/ --obfuscate            release com nomes ofuscados
    upapasta Pasta/ --password abc --rar   release com senha no RAR
    upapasta Pasta/ --dry-run              simula sem enviar nada

  Para ajuda completa:  upapasta --help
""")

_DESCRIPTION = _("UpaPasta — uploader automatizado para Usenet")

_EPILOG = _("""\
COMPORTAMENTO PADRÃO
  Pasta   → PAR2 (balanced) + upload direto (sem compactação) → NZB + NFO
  Arquivo → PAR2 + upload direto (sem compactação) → NZB + NFO
  Com --rar ou --compressor 7z: cria arquivo compactado primeiro, depois PAR2 + upload

  --obfuscate: stealth máximo — nomes aleatórios em arquivos, subjects e NZB;
              poster por artigo, ordem embaralhada, jitter de tamanho, fragmentação multigrupo.
  --obfuscate --password abc: stealth máximo + arquivo protegido com senha.
  --password sozinho: ativa compactação automaticamente (precisa de container para proteger).
  Arquivo único com --obfuscate ou --password: cria container automaticamente.

FLUXO RECOMENDADO 2026 (padrão moderno)
  upapasta Pasta/ --obfuscate --backend parpar \\
      --filepath-format common --par-profile safe

  Por quê: parpar grava a estrutura de pastas nos .par2; SABnzbd/NZBGet
  recentes reconstroem a árvore no download. Compactação é opcional — ofuscação
  forte + PAR2 já protege contra scans automáticos de copyright. Use --rar
  ou --compressor 7z apenas se precisar de senha (casos legados).

  No SABnzbd: desative "Recursive Unpacking" e revise "Unwanted Extensions".
  Use --rename-extensionless se houver arquivos sem extensão (evita .txt do SAB).

EXEMPLOS
  upapasta Pasta/ --obfuscate                 fluxo moderno (recomendado)
  upapasta Filme.2024/ --rar                  pasta como release único (força RAR)
  upapasta Filme.2024/ --7z                   pasta como release único (força 7z)
  upapasta Episodio.S01E01.mkv               arquivo único, sem compactação
  upapasta A.mkv B.mkv C.mkv                múltiplos arquivos, processamento sequencial
  upapasta Pasta/ --password "abc123"         compactado com senha (usa compressor padrão)
  upapasta Pasta/ --compress                  compacta pasta usando compressor padrão
""")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "inputs",
        nargs="*",
        metavar=_("input"),
        help=_(
            "Arquivo(s) ou pasta(s) a fazer upload. Múltiplos caminhos processados em sequência (ou paralelo com --jobs)."
        ),
    )
    p.add_argument(
        "--config",
        action="store_true",
        help=_("Abre o wizard de configuração (permite reconfigurar credenciais e opções)"),
    )
    p.add_argument(
        "--stats",
        action="store_true",
        help=_("Exibe estatísticas agregadas do histórico de uploads (history.jsonl)"),
    )
    p.add_argument(
        "--test-connection",
        action="store_true",
        help=_("Testa conectividade com o servidor NNTP (valida host, porta e credenciais)"),
    )
    p.add_argument(
        "--insecure",
        action="store_true",
        help=_(
            "Desativa verificação de certificado SSL em --test-connection (use apenas para testes)"
        ),
    )
    # ── Opções essenciais ────────────────────────────────────────────────────
    essential = p.add_argument_group(_("opções essenciais"))
    essential.add_argument(
        "--profile",
        type=str,
        default=None,
        help=_("Usa um perfil de configuração nomeado (~/.config/upapasta/<profile>.env)"),
    )
    essential.add_argument(
        "--watch",
        action="store_true",
        help=_(
            "Modo daemon: monitora <input> continuamente e processa novos itens automaticamente. "
            "Incompatível com --each/--season. Ctrl+C encerra."
        ),
    )
    essential.add_argument(
        "--each",
        action="store_true",
        help=_(
            "Processa cada arquivo da pasta individualmente. "
            "Ideal para temporadas: cada episódio vira um release separado com seu próprio NZB."
        ),
    )
    essential.add_argument(
        "--obfuscate",
        action="store_true",
        help=_(
            "Ofuscação máxima: nomes aleatórios nos arquivos, subjects da Usenet e dentro do NZB. "
            "Nenhum nome original visível em indexadores. "
            "Inclui: poster aleatório por artigo, ordem embaralhada, jitter de tamanho e fragmentação multigrupo. "
            "Downloaders modernos (SABnzbd/NZBGet) usam PAR2 para renomear automaticamente após download."
        ),
    )
    essential.add_argument(
        "--strong-obfuscate",
        action="store_true",
        help=_("Obsoleto. Use --obfuscate (comportamento idêntico desde v0.28.0)."),
    )
    essential.add_argument(
        "--password",
        nargs="?",
        const="__random__",
        default=None,
        metavar=_("SENHA"),
        help=_(
            "Senha para o arquivo compactado (injetada no NZB para extração automática). "
            "Ativa automaticamente a compactação (precisa compactar para proteger com senha). "
            "Sem argumento, gera uma senha aleatória de 16 caracteres."
        ),
    )
    comp_group = essential.add_mutually_exclusive_group()
    comp_group.add_argument(
        "--rar",
        action="store_true",
        help=_("Cria RAR antes do upload (ignora padrão do .env)."),
    )
    comp_group.add_argument(
        "--7z",
        dest="sevenzip",
        action="store_true",
        help=_("Cria 7z antes do upload (ignora padrão do .env)."),
    )
    comp_group.add_argument(
        "-c",
        "--compress",
        action="store_true",
        help=_(
            "Ativa compactação usando o compressor padrão definido no .env (ou RAR se não definido)."
        ),
    )
    essential.add_argument(
        "--skip-rar",
        action="store_true",
        dest="skip_rar_deprecated",
        help=_("[DEPRECATED: use ausência de --rar] Não cria RAR."),
    )
    essential.add_argument(
        "--dry-run",
        action="store_true",
        help=_("Simula todo o processo sem criar ou enviar arquivos."),
    )

    # ── Opções de ajuste ─────────────────────────────────────────────────────
    tuning = p.add_argument_group(_("opções de ajuste"))
    tuning.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar=_("N"),
        help=_(
            "Número de uploads paralelos quando múltiplos inputs são fornecidos (padrão: 1 = sequencial)"
        ),
    )
    tuning.add_argument(
        "--par-profile",
        choices=("fast", "balanced", "safe"),
        default="balanced",
        help=_("Perfil PAR2: fast=5%%, balanced=10%% (padrão), safe=20%%"),
    )
    tuning.add_argument(
        "-r",
        "--redundancy",
        type=int,
        default=None,
        metavar=_("PERCENT"),
        help=_("Redundância PAR2 em %% (sobrescreve --par-profile)"),
    )
    tuning.add_argument(
        "--keep-files",
        action="store_true",
        help=_("Mantém RAR e PAR2 após o upload"),
    )
    tuning.add_argument(
        "--log-file",
        default=None,
        metavar=_("PATH"),
        help=_("Grava log completo da sessão em arquivo"),
    )
    tuning.add_argument(
        "--upload-retries",
        type=int,
        default=0,
        metavar=_("N"),
        help=_("Tentativas extras de upload em caso de falha (padrão: 0)"),
    )
    tuning.add_argument(
        "--verbose",
        action="store_true",
        help=_("Ativa log de debug detalhado"),
    )
    tuning.add_argument(
        "--watch-interval",
        type=int,
        default=30,
        metavar=_("N"),
        help=_("Intervalo de varredura do --watch em segundos (padrão: 30)"),
    )
    tuning.add_argument(
        "--watch-stable",
        type=int,
        default=60,
        metavar=_("N"),
        help=_("Segundos que o tamanho deve ser estável antes de processar (padrão: 60)"),
    )

    # ── Opções avançadas ─────────────────────────────────────────────────────
    advanced = p.add_argument_group(_("opções avançadas"))
    advanced.add_argument(
        "--backend",
        choices=("parpar", "par2"),
        default="parpar",
        help=_("Backend PAR2: parpar (padrão) ou par2"),
    )
    advanced.add_argument(
        "--post-size",
        default=None,
        metavar=_("SIZE"),
        help=_("Tamanho alvo de post (ex: 20M, 700K — sobrescreve perfil)"),
    )
    advanced.add_argument(
        "--par-slice-size",
        default=None,
        metavar=_("SIZE"),
        help=_("Override manual do slice PAR2 (ex: 512K, 1M, 2M)"),
    )
    advanced.add_argument(
        "--rar-threads",
        type=int,
        default=None,
        metavar=_("N"),
        help=_("Threads para RAR (padrão: CPUs disponíveis)"),
    )
    advanced.add_argument(
        "--par-threads",
        type=int,
        default=None,
        metavar=_("N"),
        help=_("Threads para PAR2 (padrão: CPUs disponíveis)"),
    )
    advanced.add_argument(
        "--max-memory",
        type=int,
        default=None,
        metavar=_("MB"),
        help=_("Limite de memória para PAR2 em MB (padrão: automático)"),
    )
    advanced.add_argument(
        "-s",
        "--subject",
        default=None,
        help=_("Assunto da postagem (padrão: nome do arquivo/pasta)"),
    )
    advanced.add_argument(
        "-g",
        "--group",
        default=None,
        help=_("Newsgroup (padrão: do .env)"),
    )
    advanced.add_argument(
        "--nzb-conflict",
        choices=("rename", "overwrite", "fail"),
        default=None,
        help=_("Comportamento quando .nzb já existe: rename (padrão), overwrite, fail"),
    )
    advanced.add_argument(
        "--tmdb",
        action="store_true",
        help=_(
            "Busca metadados no TMDb (sinopse, poster, etc.) para enriquecer o .nfo (requer API Key no .env)."
        ),
    )
    advanced.add_argument(
        "--tmdb-id",
        type=int,
        help=_("Força um ID específico do TMDb para a busca de metadados (implica --tmdb)."),
    )
    advanced.add_argument(
        "--tmdb-search",
        metavar=_("TERMO"),
        help=_("Busca manual por filmes/séries no TMDb e lista os resultados e IDs."),
    )
    advanced.add_argument(
        "--nfo-template",
        metavar=_("PATH"),
        help=_("Caminho para um arquivo .txt a ser usado como template para o .nfo."),
    )
    advanced.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        metavar=_("PATH"),
        help=_("Caminho alternativo para o .env (padrão: ~/.config/upapasta/.env)"),
    )
    advanced.add_argument(
        "--upload-timeout",
        type=int,
        default=None,
        metavar=_("N"),
        help=_("Timeout de conexão para nyuu em segundos"),
    )
    advanced.add_argument(
        "-f",
        "--force",
        action="store_true",
        help=_("Sobrescreve RAR/PAR2 existentes"),
    )
    advanced.add_argument(
        "--skip-par",
        action="store_true",
        help=_("Pula geração de paridade"),
    )
    advanced.add_argument(
        "--skip-upload",
        action="store_true",
        help=_("Pula upload para Usenet"),
    )
    advanced.add_argument(
        "--filepath-format",
        choices=("common", "keep", "basename", "outrel"),
        default="common",
        help=_(
            "Como o parpar grava paths nos .par2 (default: common). "
            "common=descarta prefixo comum (preserva subpastas relativas); "
            "keep=preserva o caminho completo; basename=descarta paths (flat); "
            "outrel=relativo à saída. Ignorado quando backend=par2."
        ),
    )
    advanced.add_argument(
        "--parpar-args",
        default=None,
        metavar=_("STR"),
        help=_(
            'Args extras repassados ao parpar, ex: --parpar-args "--noindex --foo=bar". '
            "Tokenizado via shlex. Ignorado quando backend=par2."
        ),
    )
    advanced.add_argument(
        "--nyuu-args",
        default=None,
        metavar=_("STR"),
        help=_(
            'Args extras repassados ao nyuu, ex: --nyuu-args "--article-threads=8 --queue=20". '
            "Tokenizado via shlex."
        ),
    )
    advanced.add_argument(
        "--rename-extensionless",
        action="store_true",
        help=_(
            "Renomeia arquivos sem extensão para .bin antes do upload (reverte ao final). "
            "Evita que o SABnzbd adicione .txt em arquivos sem extensão."
        ),
    )
    advanced.add_argument(
        "--resume",
        action="store_true",
        help=_(
            "Retoma upload interrompido: detecta arquivos já postados via NZB parcial "
            "e faz upload apenas dos restantes, mesclando os NZBs ao final."
        ),
    )

    return p.parse_args()


def check_dependencies(pack_needed: bool = True, compressor: str = "rar") -> bool:
    """Verifica se os binários necessários estão no PATH."""
    required_commands = ["nyuu", "parpar"]
    if pack_needed:
        if compressor == "7z":
            from .make7z import find_7z

            if not find_7z():
                required_commands.append("7z")
        else:
            required_commands.append("rar")

    missing_commands = []
    for cmd in required_commands:
        if not shutil.which(cmd):
            missing_commands.append(cmd)

    if missing_commands:
        print(_("❌ Dependências não encontradas:"))
        for cmd in missing_commands:
            print(_("  - '{cmd}' não está instalado ou não está no PATH.").format(cmd=cmd))
        print(_("\n   Por favor, instale as dependências e tente novamente."))
        print(_("   Você pode encontrar instruções de instalação em INSTALL.md"))
        return False

    # Verificação de dependências opcionais (para NFO)
    optional_commands = ["mediainfo", "ffprobe"]
    missing_optional = [cmd for cmd in optional_commands if not shutil.which(cmd)]
    if missing_optional:
        print(
            _("⚠️  Dependências opcionais ausentes: {missing}").format(
                missing=", ".join(missing_optional)
            )
        )
        print(_("   A geração de arquivos .nfo será limitada ou ignorada."))
    else:
        print(_("✅ Todas as dependências (incluindo opcionais) foram encontradas."))

    return True


def _validate_flags(args: argparse.Namespace) -> bool:
    """Valida combinações de flags incompatíveis. Retorna False se há erro fatal."""
    # Normalizar inputs em lista; criar args.input para compatibilidade
    inputs: list[str] = getattr(args, "inputs", []) or []
    args.input = inputs[0] if inputs else None

    # Backward compatibility: --skip-rar → sem --rar
    if getattr(args, "skip_rar_deprecated", False):
        print(_("⚠️  --skip-rar está deprecado. O padrão já é sem RAR."))
        print(_("   Para usar RAR, adicione --rar explicitamente."))
        args.rar = False

    # --password sem argumento gera senha aleatória
    if args.password == "__random__":
        import secrets
        import string

        chars = string.ascii_letters + string.digits
        args.password = "".join(secrets.choice(chars) for _ in range(16))
        print(_("🔑  Senha gerada automaticamente: {password}").format(password=args.password))

    # --password ativa compactação automaticamente (precisa de container para proteger com senha)
    if args.password and not args.rar and not getattr(args, "sevenzip", False):
        print(_("ℹ️  --password ativa compactação automaticamente (usa compressor padrão do .env)."))
        # Ativamos a flag interna de compressão genérica
        args.compress = True

    # Se o usuário pediu --rar ou --7z, garantimos que a lógica de "precisa compactar" seja seguida
    if args.rar or getattr(args, "sevenzip", False):
        args.compress = True
    # --strong-obfuscate é deprecated desde v0.28.0; --obfuscate já aplica ofuscação máxima
    if getattr(args, "strong_obfuscate", False):
        args.obfuscate = True
        print(
            _(
                "⚠️  --strong-obfuscate está obsoleto desde v0.28.0. "
                "Use --obfuscate (comportamento idêntico)."
            )
        )

    # --jobs requer múltiplos inputs
    jobs = getattr(args, "jobs", 1)
    if jobs < 1:
        print(_("❌  --jobs deve ser ≥ 1."))
        return False
    if jobs > 1 and len(inputs) < 2:
        print(_("⚠️  --jobs > 1 é ignorado com apenas um input."))

    # --each e --watch requerem exatamente um input
    if getattr(args, "each", False):
        if len(inputs) > 1:
            print(_("❌  --each requer exatamente um input (pasta)."))
            return False
        if not args.input or not Path(args.input).is_dir():
            print(_("❌  --each requer uma pasta como entrada."))
            return False

    if args.watch:
        if len(inputs) > 1:
            print(_("❌  --watch requer exatamente um input (pasta)."))
            return False
        if not args.input or not Path(args.input).is_dir():
            print(_("❌  --watch requer uma pasta como entrada."))
            return False
        if getattr(args, "each", False):
            print(_("❌  --watch é incompatível com --each."))
            return False

    if args.obfuscate and not args.rar:
        # Em 2026 esse fluxo é o recomendado: ofuscação externa nos nomes que
        # vão para os headers NNTP + paths preservados dentro dos .par2 pelo
        # parpar (filepath-format). Não há ofuscação "parcial" — a estrutura
        # interna fica protegida pelo próprio mecanismo do parpar.
        print(
            _(
                "✅ Fluxo moderno: --obfuscate (sem RAR).\n"
                "   Nomes externos ofuscados; estrutura preservada via parpar."
            )
        )

    # --tmdb-id implica --tmdb
    if getattr(args, "tmdb_id", None):
        args.tmdb = True

    return True
