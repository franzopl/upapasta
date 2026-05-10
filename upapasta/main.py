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
from .i18n import _
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
    mode = _("parallel ×{jobs}").format(jobs=jobs) if jobs > 1 else _("sequential")
    print(_("📦 Multi-input: {total} item(s) — {mode}").format(total=total, mode=mode))
    failed: list[str] = []

    if jobs <= 1:
        for i, item_path in enumerate(inputs, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}/{total}] {Path(item_path).name}")
            print("=" * 60)
            try:
                rc = _run_single_input(args, item_path, env_file)
            except KeyboardInterrupt:
                print(_("\n⚠️  Interrupted by user."))
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
                    print(_("\n⚠️  Interrupted by user."))
                    return 130
                if rc != 0:
                    with lock_print:
                        failed.append(Path(item_path).name)

    if failed:
        print(
            _("\n❌  {failed_count}/{total} item(s) failed:").format(
                failed_count=len(failed), total=total
            )
        )
        for name in failed:
            print(f"    • {name}")
        return 1

    print(_("\n✅  {total}/{total} item(s) completed successfully.").format(total=total))
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
            print(_("❌ Incomplete credentials. Run 'upapasta --config' first."))
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

    if getattr(args, "tmdb_search", None):
        from .tmdb import parse_title_and_year, search_media

        env_vars = load_env_file(env_file)
        api_key = env_vars.get("TMDB_API_KEY")
        if not api_key:
            print(_("❌ Erro: --tmdb-search requer 'TMDB_API_KEY' no seu .env."))
            sys.exit(1)

        query = args.tmdb_search
        title, year = parse_title_and_year(query)
        print(_("🔍 Buscando no TMDb: '{title}'...").format(title=title))

        # Busca em ambos os tipos para utilitário
        all_results = []
        for mtype in ("movie", "tv"):
            ignore_item, suggestions = search_media(
                api_key, title, year=year, media_type=mtype, strict=False
            )
            for s in suggestions:
                s["_mtype"] = mtype
                all_results.append(s)

        if not all_results:
            print(_("❌ Nenhum resultado encontrado."))
        else:
            print(_("\nResultados encontrados:"))
            for s in all_results[:10]:
                s_title = s.get("title") or s.get("name")
                s_date = s.get("release_date") or s.get("first_air_date") or ""
                s_year = s_date[:4] if len(s_date) >= 4 else "N/A"
                s_id = s.get("id")
                s_type = "Filme" if s["_mtype"] == "movie" else "Série"
                print(f"  [{s_type}] {s_title} ({s_year}) ID: {s_id}")

        sys.exit(0)

    # Sem argumentos: exibe uso amigável e sai
    if not getattr(args, "inputs", None):
        print(_USAGE_SHORT)
        sys.exit(0)

    setup_logging(verbose=getattr(args, "verbose", False), log_file=getattr(args, "log_file", None))

    if not _validate_flags(args):
        sys.exit(1)

    # Carrega env_vars antecipadamente para decidir dependências e compressor
    env_vars = load_env_file(resolve_env_file(getattr(args, "env_file", None)))

    # Decisão do compressor
    if getattr(args, "rar", False):
        final_compressor = "rar"
    elif getattr(args, "sevenzip", False):
        final_compressor = "7z"
    else:
        final_compressor = env_vars.get("DEFAULT_COMPRESSOR", "rar")

    # Decisão se precisa de empacotamento
    needs_pack = getattr(args, "compress", False)
    try:
        p = Path(args.input)
        # Se for pasta e não pediu --skip-rar, precisa de pack
        if p.exists() and p.is_dir() and not getattr(args, "skip_rar_deprecated", False):
            needs_pack = True
        # Se for arquivo único mas pediu obfuscate, também ativa pack por segurança (evitar vazar ext)
        if p.exists() and p.is_file() and args.obfuscate:
            needs_pack = True
    except Exception:
        pass

    if not check_dependencies(needs_pack, compressor=final_compressor):
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
        skip_extensions = {".par2", ".nfo", ".nzb"}
        skip_patterns = [".vol", ".part"]

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
            items = sorted(
                f for f in folder.iterdir() if not f.name.startswith(".") and not should_skip(f)
            )

        if not items:
            print(_("❌  No items found in: {folder}").format(folder=folder))
            sys.exit(1)

        mode_name = "--each" if args.each else "--season"
        print(
            _("📂 Mode {mode}: {count} item(s) in {folder}").format(
                mode=mode_name, count=len(items), folder=folder.name
            )
        )
        failed: list[str] = []
        # Tracking em memória: evita redescoberta frágil via glob
        # season_all_nzbs: todos os episódios (arquivo + pasta) — para o merge
        # season_folder_eps: só episódios-pasta — precisam de prefixo no season NZB
        season_all_nzbs: list[str] = []
        season_folder_eps: list[tuple[str, str]] = []  # (nzb_path, ep_name)

        for i, item_path in enumerate(items, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}/{len(items)}] {item_path.name}")
            print("=" * 60)

            input_name = item_path.name
            log_path, log_fh = setup_session_log(input_name, env_file=env_file)
            rc = 1
            orch_ref: UpaPastaOrchestrator | None = None
            try:
                orchestrator = UpaPastaOrchestrator.from_args(args, str(item_path))

                # Pastas de episódio recebem prefixo no subject (ex: S01E01/video.mkv),
                # evitando colisões de nome quando os NZBs forem mesclados.
                # Arquivos únicos já têm nome distinto — prefixo não é necessário.
                if args.season and item_path.is_dir():
                    orchestrator.nzb_subject_prefix = item_path.name

                with UpaPastaSession(orchestrator) as orch:
                    rc = orch.run()
                    orch_ref = orch
            except KeyboardInterrupt:
                rc = 130
                teardown_session_log(log_fh, log_path)
                print(_("\n⚠️  Interrupted by user."))
                sys.exit(rc)
            except Exception:
                import traceback

                traceback.print_exc()
            finally:
                teardown_session_log(log_fh, log_path)

            if rc != 0:
                failed.append(item_path.name)
            elif args.season and orch_ref is not None and orch_ref.generated_nzb:
                nzb_path = orch_ref.generated_nzb
                season_all_nzbs.append(nzb_path)
                # Episódios-pasta precisam de prefixo no NZB consolidado para distinguir
                # arquivos com mesmo nome (ex: Video.mkv em S01E01 e S01E02).
                # Episódios-arquivo já têm nome único após fix_nzb_subjects — sem prefixo.
                if item_path.is_dir():
                    season_folder_eps.append((nzb_path, item_path.name))

        # No --each, falhas são fatais
        if args.each and failed:
            print(_("\n❌  {count} item(s) failed:").format(count=len(failed)))
            for name in failed:
                print(f"    • {name}")
            sys.exit(1)

        # No --season, falhas parciais são toleradas; geramos NZB com os que sucederam
        if args.season and failed:
            print(
                _("\n⚠️  {count} item(s) failed (continuing with season NZB):").format(
                    count=len(failed)
                )
            )
            for name in failed:
                print(f"    • {name}")

        # ── Pós-processamento da Temporada ────────────────────────────────────
        if args.season:
            env_vars = load_env_file(env_file)

            # Fallback para glob se o tracking em memória ficou vazio (ex: --skip-upload)
            if not season_all_nzbs:
                nzb_out_dir = env_vars.get("NZB_OUT_DIR")
                if not nzb_out_dir:
                    raw = env_vars.get("NZB_OUT")
                    nzb_out_dir = str(Path(raw).parent) if raw else None
                working_dir_path = Path(nzb_out_dir or ".").expanduser().resolve()
                # No fallback não sabemos quais eram pastas — passamos tudo para fix
                fallback_eps = collect_season_nzbs(str(working_dir_path), folder.name)
                season_all_nzbs = [p for p, _ in fallback_eps]
                season_folder_eps = fallback_eps
            else:
                working_dir_path = Path(season_all_nzbs[0]).parent

            if season_all_nzbs:
                print(f"\n{'=' * 60}")
                print(_("🌟 Finalizing Season: {folder}").format(folder=folder.name))
                print("=" * 60)

                season_nzb_name = f"{folder.name}.nzb"
                season_nzb_path = working_dir_path / season_nzb_name

                print(
                    _("📦 Merging {count} NZBs into: {name}").format(
                        count=len(season_all_nzbs), name=season_nzb_name
                    )
                )
                if merge_nzbs(season_all_nzbs, str(season_nzb_path)):
                    if args.obfuscate:
                        # Ofuscação: usa prefixos numéricos (01/, 02/...) para isolar eps no SABnzbd
                        # sem vazar os nomes originais nos subjects da Usenet.
                        numeric_eps = [
                            (nzb_path, f"{i:02d}") for i, nzb_path in enumerate(season_all_nzbs, 1)
                        ]
                        fix_season_nzb_subjects(str(season_nzb_path), numeric_eps)
                    elif season_folder_eps:
                        # Sem ofuscação: aplica prefixo de nome original só em episódios-pasta
                        # (arquivos únicos já têm subjects corretos e não precisam de tratamento).
                        fix_season_nzb_subjects(str(season_nzb_path), season_folder_eps)
                    print(_("✅ Season NZB generated successfully!"))
                else:
                    print(_("❌ Failed to generate season NZB."))

                season_nfo_path = season_nzb_path.with_suffix(".nfo")
                banner = env_vars.get("NFO_BANNER")
                print(_("📄 Generating season NFO..."))
                if generate_nfo_folder(str(folder), str(season_nfo_path), banner=banner):
                    print(_("✅ Season NFO generated: {name}").format(name=season_nfo_path.name))
                else:
                    print(_("⚠️  Failed to generate season NFO."))
            elif not failed:
                print(_("⚠️  No episode NZBs found for: {folder}").format(folder=folder.name))

        sys.exit(0)

    # ── Modo --watch: daemon de monitoramento ────────────────────────────────
    if args.watch:
        try:
            _watch_loop(args, Path(args.input), args.watch_interval, args.watch_stable)
        except KeyboardInterrupt:
            print(_("\n👁  --watch closed by user."))
        sys.exit(0)

    # ── Modo normal: um único input ──────────────────────────────────────────
    try:
        rc = _run_single_input(args, args.input, env_file)
    except KeyboardInterrupt:
        rc = 130

    sys.exit(rc)


if __name__ == "__main__":
    main()
