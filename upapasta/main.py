#!/usr/bin/env python3
"""
main.py

Ponto de entrada do UpaPasta.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .cli import parse_args, check_dependencies, _validate_flags, _USAGE_SHORT
from .config import check_or_prompt_credentials, resolve_env_file, load_env_file
from .nntp_test import test_nntp_connection
from .ui import setup_logging, setup_session_log, teardown_session_log
from .orchestrator import UpaPastaOrchestrator, UpaPastaSession
from .watch import _watch_loop
from .nzb import merge_nzbs, resolve_nzb_out, fix_season_nzb_subjects
from .nfo import generate_nfo_folder


def main():
    args = parse_args()

    # Resolver arquivo de env: --profile > --env-file > padrão
    profile = getattr(args, "profile", None)
    if profile:
        env_file = resolve_env_file(profile)
    else:
        env_file = getattr(args, "env_file", None)
        if not env_file:
            env_file = resolve_env_file()

    if getattr(args, "config", False):
        check_or_prompt_credentials(env_file, force=True)
        sys.exit(0)

    if getattr(args, "test_connection", False):
        env_vars = load_env_file(env_file)
        if not all(env_vars.get(k) for k in ["NNTP_HOST", "NNTP_PORT", "NNTP_USER", "NNTP_PASS"]):
            print("❌ Credenciais incompletas. Execute 'upapasta --config' primeiro.")
            sys.exit(1)
        success, message = test_nntp_connection(
            host=env_vars["NNTP_HOST"],
            port=int(env_vars["NNTP_PORT"]),
            use_ssl=env_vars.get("NNTP_SSL", "true").lower() in ("true", "1", "yes"),
            user=env_vars["NNTP_USER"],
            password=env_vars["NNTP_PASS"],
        )
        print(message)
        sys.exit(0 if success else 1)

    # Sem argumentos: exibe uso amigável e sai
    if args.input is None:
        print(_USAGE_SHORT)
        sys.exit(0)

    setup_logging(verbose=getattr(args, "verbose", False), log_file=getattr(args, "log_file", None))

    if not _validate_flags(args):
        sys.exit(1)

    needs_rar = True
    try:
        p = Path(args.input)
        if p.exists() and p.is_file() and not args.obfuscate and not args.password:
            needs_rar = False
    except Exception:
        pass

    if not check_dependencies(needs_rar):
        sys.exit(1)

    # ── Modo --each ou --season: processa itens individualmente ──────────────
    if args.each or args.season:
        folder = Path(args.input)
        # --each foca em arquivos; --season inclui pastas (episódios podem ser pastas)
        if args.each:
            items = sorted(f for f in folder.iterdir() if f.is_file())
        else:
            items = sorted(f for f in folder.iterdir() if not f.name.startswith('.'))

        if not items:
            print(f"❌  Nenhum item encontrado em: {folder}")
            sys.exit(1)

        mode_name = "--each" if args.each else "--season"
        print(f"📂 Modo {mode_name}: {len(items)} item(ns) em {folder.name}")
        failed: list[str] = []
        nzb_episode_data: list[tuple[str, str]] = []

        for i, item_path in enumerate(items, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(items)}] {item_path.name}")
            print("=" * 60)

            input_name = item_path.name
            log_path, log_fh = setup_session_log(input_name, env_file=env_file)
            rc = 1
            try:
                orchestrator = UpaPastaOrchestrator.from_args(args, str(item_path))
                
                # No modo --season, se o item for uma pasta, usamos o nome dela como 
                # prefixo nos subjects do NZB. Isso evita colisões em NZBs mesclados
                # e preserva a estrutura de subpastas no download.
                if args.season and item_path.is_dir():
                    orchestrator.nzb_subject_prefix = item_path.name
                
                with UpaPastaSession(orchestrator) as orch:
                    rc = orch.run()
                    if rc == 0 and orch.generated_nzb:
                        nzb_episode_data.append((orch.generated_nzb, item_path.name))
            except KeyboardInterrupt:
                rc = 130
                teardown_session_log(log_fh, log_path)
                print("\n⚠️  Interrompido pelo usuário.")
                sys.exit(rc)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                teardown_session_log(log_fh, log_path)

            if rc != 0:
                failed.append(item_path.name)

        if failed:
            print(f"\n❌  {len(failed)} item(s) com falha:")
            for name in failed:
                print(f"    • {name}")
            # Se --season falhou em algum episódio, não gera o NZB da temporada
            if args.season:
                print("⚠️  NZB da temporada não será gerado devido a falhas nos episódios.")
            sys.exit(1)

        # ── Pós-processamento da Temporada ────────────────────────────────────
        if args.season and nzb_episode_data:
            print(f"\n{'='*60}")
            print(f"🌟 Finalizando Temporada: {folder.name}")
            print("=" * 60)
            
            # Resolve caminho do NZB da temporada
            env_vars = load_env_file(env_file)
            working_dir = env_vars.get("NZB_OUT_DIR") or "."
            
            # O nome do NZB da temporada é o nome da pasta
            season_nzb_name = f"{folder.name}.nzb"
            season_nzb_path = Path(working_dir) / season_nzb_name
            
            nzb_paths = [p for p, _ in nzb_episode_data]
            print(f"📦 Mesclando {len(nzb_paths)} NZBs em: {season_nzb_name}")
            if merge_nzbs(nzb_paths, str(season_nzb_path)):
                fix_season_nzb_subjects(str(season_nzb_path), nzb_episode_data)
                print(f"✅ NZB da temporada gerado com sucesso!")
            else:
                print(f"❌ Falha ao gerar NZB da temporada.")

            # Geração do NFO da temporada
            season_nfo_path = season_nzb_path.with_suffix(".nfo")
            banner = env_vars.get("NFO_BANNER")
            print(f"📄 Gerando NFO da temporada...")
            if generate_nfo_folder(str(folder), str(season_nfo_path), banner=banner):
                print(f"✅ NFO da temporada gerado: {season_nfo_path.name}")
            else:
                print(f"⚠️  Falha ao gerar NFO da temporada.")

        sys.exit(0)

    # ── Modo --watch: daemon de monitoramento ────────────────────────────────
    if args.watch:
        try:
            _watch_loop(args, Path(args.input), args.watch_interval, args.watch_stable)
        except KeyboardInterrupt:
            print("\n👁  --watch encerrado pelo usuário.")
        sys.exit(0)

    # ── Modo normal: um único input ──────────────────────────────────────────
    input_name = Path(args.input).name
    log_path, log_fh = setup_session_log(input_name, env_file=env_file)

    rc = 1
    try:
        orchestrator = UpaPastaOrchestrator.from_args(args,args.input)
        with UpaPastaSession(orchestrator) as orch:
            rc = orch.run()
    except KeyboardInterrupt:
        rc = 130
    except Exception:
        rc = 1
        import traceback
        traceback.print_exc()
    finally:
        teardown_session_log(log_fh, log_path)

    sys.exit(rc)


if __name__ == "__main__":
    main()
