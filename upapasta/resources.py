"""
resources.py

Cálculo dinâmico de threads e memória para jobs do UpaPasta.
Usa apenas stdlib + /proc/meminfo (Linux). Sem dependências externas.
"""

import os
import logging

logger = logging.getLogger("upapasta")


def get_mem_available_mb() -> int:
    """Lê MemAvailable de /proc/meminfo. Fallback conservador: 2048 MB."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except Exception as e:
        logger.warning(f"Não foi possível ler /proc/meminfo: {e}")
    return 2048


def get_total_size(path: str) -> int:
    """Tamanho total em bytes de arquivo ou pasta, sem seguir symlinks."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def calculate_optimal_resources(
    total_size_bytes: int,
    user_threads: int | None = None,
    user_memory_mb: int | None = None,
) -> dict:
    """
    Calcula threads e limite de memória para o job atual.

    Estratégia:
    - Threads: 75% da CPU para jobs pequenos, 50% para jobs massivos (>200GB),
      pois esses são I/O-bound e monopolizar CPU não ajuda.
    - Memória: 70% do disponível (60% para jobs >200GB), com mínimo de 2GB
      livres para o sistema. Cap em 8GB — parpar não se beneficia além disso.
    - conservative_mode: ativado se job >200GB ou <4GB disponíveis.

    Args:
        total_size_bytes: tamanho total da fonte em bytes.
        user_threads: override manual (--rar-threads / --par-threads).
        user_memory_mb: override manual (--max-memory).

    Returns:
        dict com threads, max_memory_mb, conservative_mode, total_gb.
    """
    cpu = os.cpu_count() or 2
    mem_avail = get_mem_available_mb()
    total_gb = total_size_bytes / (1024 ** 3)
    conservative = total_gb > 200 or mem_avail < 4096

    # Threads
    if user_threads is not None:
        threads = max(1, user_threads)
    elif total_gb > 200:
        # Jobs massivos: cap absoluto de 8 threads — parpar crasha com SIGSEGV
        # acima disso em datasets grandes (bug de concorrência no parpar).
        threads = min(8, max(4, int(cpu * 0.25)))
    elif total_gb > 100:
        threads = min(16, max(4, int(cpu * 0.40)))
    elif total_gb > 50:
        threads = max(2, int(cpu * 0.65))
    else:
        threads = max(2, int(cpu * 0.75))

    # Memória: mantém ao menos 2GB livres para o sistema
    if user_memory_mb is not None:
        max_memory_mb = max(256, user_memory_mb)
    else:
        pct = 0.60 if conservative else 0.70
        raw = int(mem_avail * pct)
        # Garantia de headroom mínimo para o sistema
        safe = min(raw, mem_avail - 2048)
        # Cap em 8GB: parpar/par2 não se beneficiam de mais
        max_memory_mb = max(512, min(safe, 8192))

    return {
        "threads": threads,
        "max_memory_mb": max_memory_mb,
        "conservative_mode": conservative,
        "total_gb": round(total_gb, 2),
    }
