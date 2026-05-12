"""
par_utils.py

Utilitários compartilhados para cálculo de parâmetros de paridade (PAR2).
"""

from __future__ import annotations

from typing import Optional, Tuple

# ── Helpers de tamanho ────────────────────────────────────────────────────────


def parse_size(s: str) -> int:
    """Converte string de tamanho (ex: '700K', '1M', '768000') para bytes."""
    s = str(s).strip()
    if not s:
        raise ValueError("string de tamanho vazia")
    unit = s[-1].upper()
    if unit == "K":
        return int(float(s[:-1]) * 1024)
    if unit == "M":
        return int(float(s[:-1]) * 1024 * 1024)
    if unit == "G":
        return int(float(s[:-1]) * 1024 * 1024 * 1024)
    return int(float(s))


def fmt_size(b: int) -> str:
    """Formata bytes para string compacta (ex: 1572864 → '1536K' ou '1M')."""
    if b % (1024 * 1024) == 0:
        return f"{b // (1024 * 1024)}M"
    if b % 1024 == 0:
        return f"{b // 1024}K"
    return str(b)


# ── Leitura de ARTICLE_SIZE do .env ──────────────────────────────────────────


def get_article_size_bytes() -> int:
    """
    Lê ARTICLE_SIZE do ~/.config/upapasta/.env.
    Retorna o valor em bytes. Fallback: 786432 (768K).
    """
    try:
        from .config import DEFAULT_ENV_FILE, load_env_file

        env = load_env_file(DEFAULT_ENV_FILE)
        raw = env.get("ARTICLE_SIZE", "").strip()
        if raw:
            return parse_size(raw)
    except Exception:
        pass
    return 786432  # 768K


# ── Cálculo dinâmico de slice size ────────────────────────────────────────────


def compute_dynamic_slice(total_bytes: int, article_size: int) -> Tuple[str, int, int]:
    """
    Calcula slice size, min-input-slices e max-input-slices para parpar.

    Regras:
      base_slice = article_size * 2
      ≤ 50 GB  → base_slice           (min_slices=60)
      ≤ 100 GB → base_slice * 1.5     (min_slices=80)
      ≤ 200 GB → base_slice * 2       (min_slices=100)
      > 200 GB → base_slice * 2.5     (min_slices=120)

    Clamp final: mínimo 1 MiB, máximo 4 MiB.
    max_input_slices fixo em 12000 (limite seguro para NZBGet/SABnzbd).

    Retorna (slice_str, min_slices, max_slices).
    """
    GB = 1024**3
    base = article_size * 2  # ex: 768K → 1.536M

    if total_bytes <= 50 * GB:
        slice_bytes = base
        min_slices = 60
    elif total_bytes <= 100 * GB:
        slice_bytes = int(base * 1.5)
        min_slices = 80
    elif total_bytes <= 200 * GB:
        slice_bytes = base * 2
        min_slices = 100
    else:
        slice_bytes = int(base * 2.5)
        min_slices = 120

    # Clamp: 1 MiB ≤ slice ≤ 4 MiB
    slice_bytes = max(1024 * 1024, min(slice_bytes, 4 * 1024 * 1024))

    return fmt_size(slice_bytes), min_slices, 12000


# ── Memória disponível ────────────────────────────────────────────────────────


def get_parpar_memory_limit() -> Optional[str]:
    """
    Retorna limite de memória seguro para parpar (75% da RAM livre).
    Mínimo 256M, máximo 3G. Retorna None se não conseguir detectar.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    safe_mb = max(256, min(int((kb // 1024) * 0.75), 3 * 1024))
                    if safe_mb >= 1024 and safe_mb % 1024 == 0:
                        return f"{safe_mb // 1024}G"
                    return f"{safe_mb}M"
    except Exception:
        pass
    return None
