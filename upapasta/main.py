#!/usr/bin/env python3
"""
main.py

Ponto de entrada do UpaPasta.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .catalog import print_stats
from .cli import _USAGE_SHORT, _validate_flags, check_dependencies, parse_args
from .config import check_or_prompt_credentials, load_env_file, resolve_env_file
from .nfo import generate_nfo_folder
from .nntp_test import test_nntp_connection
from .nzb import collect_season_nzbs, fix_season_nzb_subjects, merge_nzbs
from .orchestrator import UpaPastaOrchestrator, UpaPastaSession
from .ui import setup_logging, setup_session_log, teardown_session_log
from .watch import _watch_loop


def _run_single_input(args: Any, item_path: str, env_file: str) -> int:
    """Processa um único input e retorna o código de saída."""
    input_name = Path(item_path).name
    log_path, log_fh = setup_session_log(input_name, env_file=env_file)
    rc = 1
    try:
        orchestrator = UpaPastaOrchestrator.from_args(args, item_path)
        with UpaPastaSession(orchestrator) as orch:
            rc = orch.run()
    except KeyboardInterrupt:
        rc = 130
        teardown_session_log(log_fh, log_path)
        raise
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        teardown_session_log(log_fh, log_path)
    return rc


def _run_multi_input(args: Any, inputs: list[str], env_file: str, jobs: int) -> int:
    """Processa múltiplos inputs em sequência (jobs=1) ou em paralelo (jobs>1)."""
    total = len(inputs)
    print(f"📦 Multi-input: {total} item(s) — {'paralelo ×' + str(jobs) if jobs > 1 else 'sequencial'}")
    failed: list[str] = []

    if jobs <= 1:
        for i, item_path in enumerate(inputs, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{total}] {Path(item_path).name}")
            print("=" * 60)
            try:
                rc = _run_single_input(args, item_path, env_file)
            except KeyboardInterrupt:
                print("\n⚠️  Interrompido pelo usuário.")
                return 130
            if rc != 0:
                failed.append(Path(item_path).name)
    else:
        # Paralelo: ThreadPoolExecutor com jobs workers
        lock_print = __import__("threading").Lock()

        def _worker(item_path: str) -> tuple[str, int]:
            try:
                rc = _run_single_input(args, item_path, env_file)
            except KeyboardInterrupt:
                rc = 130
            return item_path, rc

        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = {executor.submit(_worker, p): p for p in inputs}
            for future in as_completed(futures):
                item_path, rc = future.result()
                if rc == 130:
                    executor.shutdown(wait=False, cancel_futures=True)
                    print("\n⚠️  Interrompido pelo usuário.")
                    return 130
                if rc != 0:
                    with lock_print:
                        failed.append(Path(item_path).name)

    if failed:
        print(f"\n❌  {len(failed)}/{total} item(s) com falha:")
        for name in failed:
            print(f"    • {name}")
        return 1

    print(f"\n✅  {total}/{total} item(s) concluídos com sucesso.")
    return 0


def main() -> None:
    args = parse_args()

    # Resolver arquivo de env: --profile > --env-file > padrão
    profile: str | None = getattr(args, "profile", None)
    if profile:
        env_file: str = resolve_env_file(profile)
    else:
        env_file_arg = getattr(args, "env_file", None)
        if env_file_arg:
            env_file = str(env_file_arg)
        else:
            env_file = resolve_env_file()

    if getattr(args, "config", False):
        check_or_prompt_credentials(env_file, force=True)
        sys.exit(0)

    if getattr(args, "stats", False):
        print_stats()
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
            insecure=getattr(args, "insecure", False),
        )
        print(message)
        sys.exit(0 if success else 1)

    # Sem argumentos: exibe uso amigável e sai
    if not getattr(args, "inputs", None):
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

    # ── Modo multi-input: múltiplos caminhos posicionais ─────────────────────
    all_inputs: list[str] = getattr(args, "inputs", []) or []
    if len(all_inputs) > 1:
        jobs = getattr(args, "jobs", 1)
        rc = _run_multi_input(args, all_inputs, env_file, jobs)
        sys.exit(rc)

    # ── Modo --each ou --season: processa itens individualmente ──────────────
    if args.each or args.season:
        folder = Path(args.input)
        # Extensões de arquivos gerados que devem ser ignorados
        skip_extensions = {'.par2', '.nfo', '.nzb'}
        skip_patterns = ['.vol', '.part']

        def should_skip(f: Path) -> bool:
            if any(f.name.endswith(ext) for ext in skip_extensions):
                return True
            if any(pattern in f.name for pattern in skip_patterns):
                return True
            return False

        # --each foca em arquivos; --season inclui pastas (episódios podem ser pastas)
        if args.each:
            items = sorted(f for f in folder.iterdir() if f.is_file() and not should_skip(f))
        else:
            items = sorted(f for f in folder.iterdir() if not f.name.startswith('.') and not should_skip(f))

        if not items:
            print(f"❌  Nenhum item encontrado em: {folder}")
            sys.exit(1)

        mode_name = "--each" if args.each else "--season"
        print(f"📂 Modo {mode_name}: {len(items)} item(ns) em {folder.name}")
        failed: list[str] = []

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

        # No --each, falhas são fatais
        if args.each and failed:
            print(f"\n❌  {len(failed)} item(s) com falha:")
            for name in failed:
                print(f"    • {name}")
            sys.exit(1)

        # No --season, falhas parciais são toleradas; geramos NZB com os que sucederam
        if args.season and failed:
            print(f"\n⚠️  {len(failed)} item(s) com falha (continuando com NZB da temporada):")
            for name in failed:
                print(f"    • {name}")

        # ── Pós-processamento da Temporada ────────────────────────────────────
        if args.season:
            # Coleta NZBs de episódios gerados na pasta
            env_vars = load_env_file(env_file)
            nzb_out_dir = env_vars.get("NZB_OUT_DIR")
            if not nzb_out_dir:
                nzb_out_dir = env_vars.get("NZB_OUT")
                if nzb_out_dir:
                    # Se NZB_OUT é um template, extrai o diretório
                    nzb_out_dir = str(Path(nzb_out_dir).parent)
            working_dir = nzb_out_dir or "."
            working_dir_path = Path(working_dir).expanduser().resolve()

            episode_data = collect_season_nzbs(str(working_dir_path), folder.name)

            if episode_data:
                print(f"\n{'='*60}")
                print(f"🌟 Finalizando Temporada: {folder.name}")
                print("=" * 60)

                # O nome do NZB da temporada é o nome da pasta
                season_nzb_name = f"{folder.name}.nzb"
                season_nzb_path = working_dir_path / season_nzb_name

                nzb_paths = [p for p, _ in episode_data]
                print(f"📦 Mesclando {len(nzb_paths)} NZBs em: {season_nzb_name}")
                if merge_nzbs(nzb_paths, str(season_nzb_path)):
                    fix_season_nzb_subjects(str(season_nzb_path), episode_data)
                    print("✅ NZB da temporada gerado com sucesso!")
                else:
                    print("❌ Falha ao gerar NZB da temporada.")

                # Geração do NFO da temporada
                season_nfo_path = season_nzb_path.with_suffix(".nfo")
                banner = env_vars.get("NFO_BANNER")
                print("📄 Gerando NFO da temporada...")
                if generate_nfo_folder(str(folder), str(season_nfo_path), banner=banner):
                    print(f"✅ NFO da temporada gerado: {season_nfo_path.name}")
                else:
                    print("⚠️  Falha ao gerar NFO da temporada.")
            elif not failed:
                print(f"⚠️  Nenhum NZB de episódio encontrado em {working_dir_path}")

        sys.exit(0)

    # ── Modo --watch: daemon de monitoramento ────────────────────────────────
    if args.watch:
        try:
            _watch_loop(args, Path(args.input), args.watch_interval, args.watch_stable)
        except KeyboardInterrupt:
            print("\n👁  --watch encerrado pelo usuário.")
        sys.exit(0)

    # ── Modo normal: um único input ──────────────────────────────────────────
    try:
        rc = _run_single_input(args, args.input, env_file)
    except KeyboardInterrupt:
        rc = 130

    sys.exit(rc)


if __name__ == "__main__":
    main()
