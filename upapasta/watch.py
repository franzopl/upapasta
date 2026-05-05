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
    print("👁️  MODO WATCH ATIVADO")
    print("═" * 60)
    print(f"📁 Pasta:       {folder}")
    print(f"⏱️  Intervalo:   {interval}s")
    print(f"⚖️  Estabilidade: {stable_secs}s")
    print(f"🚫 Ignorados:   {len(processed)} item(ns) já existentes")
    print("💡 Dica:        Mova arquivos para a pasta para iniciar o upload")
    print("🛑 Atalho:      Pressione Ctrl+C para encerrar")
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
                    stdout_real.write(f"\r[{ts}] {char} Ocioso: aguardando novos arquivos...   ")
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

        print(f"\n{'🔔' if len(new_items) == 1 else '🔔🔔'} {len(new_items)} novo(s) item(ns) detectado(s)!")
        for item in new_items:
            print(f"  • {item.name}")

        # Mede tamanho de todos os candidatos ANTES do sleep de estabilidade
        print(f"\n⚖️  Verificando estabilidade dos arquivos ({stable_secs}s)...")
        sizes_before: dict[Path, int] = {item: _item_size(item) for item in new_items}
        time.sleep(stable_secs)

        for item in new_items:
            size_after = _item_size(item)
            if sizes_before[item] == size_after and size_after > 0:
                print(f"\n🚀 Iniciando processamento: {item.name}")
                print("─" * 40)

                log_path, log_fh = setup_session_log(item.name, env_file=args.env_file)
                try:
                    orch = UpaPastaOrchestrator.from_args(args, str(item))
                    with UpaPastaSession(orch) as o:
                        rc = o.run()
                        if rc == 0:
                            print(f"\n✅ Concluído com sucesso: {item.name}")
                        else:
                            print(f"\n❌ Falha no processamento (rc={rc}): {item.name}")
                except KeyboardInterrupt:
                    teardown_session_log(log_fh, log_path)
                    raise
                except Exception:
                    print(f"\n💥 Erro inesperado ao processar {item.name}:")
                    import traceback
                    traceback.print_exc()
                finally:
                    teardown_session_log(log_fh, log_path)

                print("\n" + "─" * 40)
                print("🔄 Retornando ao modo watch...")
                # Marca como processado independente de sucesso (evita retry infinito)
                processed.add(item)
            else:
                if size_after <= 0:
                    print(f"⚠️  {item.name}: arquivo vazio ou inacessível, ignorando.")
                    processed.add(item)
                else:
                    print(f"⏳ {item.name}: tamanho ainda mudando, aguardando estabilidade...")

        # Força um pequeno delay antes da próxima varredura para não saturar I/O
        time.sleep(2)
