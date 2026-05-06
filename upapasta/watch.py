"""
watch.py

Lógica do modo daemon (--watch) para monitoramento automático de pastas.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from .i18n import _
from .orchestrator import UpaPastaOrchestrator, UpaPastaSession
from .ui import setup_session_log, teardown_session_log


def _item_size(path: Path) -> int:
    """Tamanho total em bytes de arquivo ou pasta (recursivo)."""
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return -1
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total



def _watch_loop(args: argparse.Namespace, folder: Path, interval: int, stable_secs: int) -> None:
    """Monitora folder via polling e processa novos itens automaticamente."""
    try:
        processed: set[Path] = set(folder.iterdir())  # baseline: ignora o que já existe
    except OSError:
        processed = set()

    print("\n" + "═" * 60)
    print(_("👁️  WATCH MODE ACTIVATED"))
    print("═" * 60)
    print(_("📁 Folder:       {path}").format(path=folder))
    print(_("⏱️  Interval:     {interval}s").format(interval=interval))
    print(_("⚖️  Stability:    {stable}s").format(stable=stable_secs))
    print(_("🚫 Ignored:      {count} existing item(s)").format(count=len(processed)))
    print(_("💡 Hint:         Move files to the folder to start upload"))
    print(_("🛑 Shortcut:     Press Ctrl+C to stop"))
    print("═" * 60 + "\n")

    spinner = ["|", "/", "-", "\\"]
    spinner_idx = 0

    while True:
        try:
            current = set(folder.iterdir())
        except OSError:
            time.sleep(interval)
            continue

        new_items = sorted(current - processed)

        if not new_items:
            # Mostra spinner apenas no terminal (não polui log nem gera nova linha)
            if sys.stdout.isatty():
                ts = datetime.now().strftime("%H:%M:%S")
                char = spinner[spinner_idx % len(spinner)]
                # Use sys.__stdout__ para garantir que o spinner não vá para o arquivo de log
                stdout_real = sys.__stdout__
                if stdout_real is not None:
                    stdout_real.write(f"\r[{ts}] {char} " + _("Idle: watching for new files...   "))
                    stdout_real.flush()
                spinner_idx += 1

            # Divide o intervalo em pequenos passos para o spinner ser fluido
            for _ in range(max(1, interval * 2)):
                if list(folder.iterdir()) != list(current): # Pequena otimização: checa se algo mudou antes do sleep total
                    break
                time.sleep(0.5)
            continue

        # Limpa a linha do spinner antes de mostrar novos itens
        if sys.stdout.isatty():
            stdout_real = sys.__stdout__
            if stdout_real is not None:
                stdout_real.write("\r" + " " * 60 + "\r")
                stdout_real.flush()

        emoji = '🔔' if len(new_items) == 1 else '🔔🔔'
        print(_("\n{emoji} {count} new item(s) detected!").format(emoji=emoji, count=len(new_items)))
        for item in new_items:
            print(f"  • {item.name}")

        # Mede tamanho de todos os candidatos ANTES do sleep de estabilidade
        print(_("\n⚖️  Checking file stability ({stable}s)...").format(stable=stable_secs))
        sizes_before: dict[Path, int] = {item: _item_size(item) for item in new_items}
        time.sleep(stable_secs)

        for item in new_items:
            size_after = _item_size(item)
            if sizes_before[item] == size_after and size_after > 0:
                print(_("\n🚀 Starting process: {name}").format(name=item.name))
                print("─" * 40)

                log_path, log_fh = setup_session_log(item.name, env_file=args.env_file)
                try:
                    orch = UpaPastaOrchestrator.from_args(args, str(item))
                    with UpaPastaSession(orch) as o:
                        rc = o.run()
                        if rc == 0:
                            print(_("\n✅ Successfully completed: {name}").format(name=item.name))
                        else:
                            print(_("\n❌ Processing failed (rc={rc}): {name}").format(rc=rc, name=item.name))
                except KeyboardInterrupt:
                    teardown_session_log(log_fh, log_path)
                    raise
                except Exception:
                    print(_("\n💥 Unexpected error processing {name}:").format(name=item.name))
                    import traceback
                    traceback.print_exc()
                finally:
                    teardown_session_log(log_fh, log_path)

                print("\n" + "─" * 40)
                print(_("🔄 Returning to watch mode..."))
                # Marca como processado independente de sucesso (evita retry infinito)
                processed.add(item)
            else:
                if size_after <= 0:
                    print(_("⚠️  {name}: empty or inaccessible file, ignoring.").format(name=item.name))
                    processed.add(item)
                else:
                    print(_("⏳ {name}: size still changing, waiting for stability...").format(name=item.name))

        # Força um pequeno delay antes da próxima varredura para não saturar I/O
        time.sleep(2)
