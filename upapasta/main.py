#!/usr/bin/env python3
"""
main.py

Ponto de entrada do UpaPasta.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .cli import parse_args, check_dependencies, _validate_flags, _USAGE_SHORT
from .ui import setup_logging, setup_session_log, teardown_session_log
from .orchestrator import UpaPastaOrchestrator, UpaPastaSession
from .watch import _watch_loop, _make_orchestrator


def main():
    args = parse_args()

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

    # ── Modo --each: processa cada arquivo da pasta individualmente ──────────
    if args.each:
        folder = Path(args.input)
        files = sorted(f for f in folder.iterdir() if f.is_file())
        if not files:
            print(f"❌  Nenhum arquivo encontrado em: {folder}")
            sys.exit(1)

        print(f"📂 Modo --each: {len(files)} arquivo(s) em {folder.name}")
        failed: list[str] = []

        for i, file_path in enumerate(files, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(files)}] {file_path.name}")
            print("=" * 60)

            input_name = file_path.name
            log_path, log_fh = setup_session_log(input_name, env_file=args.env_file)
            rc = 1
            try:
                orchestrator = _make_orchestrator(args, str(file_path))
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
                failed.append(file_path.name)

        if failed:
            print(f"\n❌  {len(failed)} arquivo(s) com falha:")
            for name in failed:
                print(f"    • {name}")
            sys.exit(1)
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
    log_path, log_fh = setup_session_log(input_name, env_file=args.env_file)

    rc = 1
    try:
        orchestrator = _make_orchestrator(args, args.input)
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
