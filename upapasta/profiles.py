"""
profiles.py

Perfis de otimização PAR2 (fast / balanced / safe).
"""

from __future__ import annotations

PROFILES: dict[str, dict] = {
    "fast": {
        "description": "Máxima velocidade (ideal para upload urgente)",
        "slice_size": "20M",
        "redundancy": 5,
        "post_size": "100M",
    },
    "balanced": {
        # slice_size=None → makepar.py calcula dinamicamente via ARTICLE_SIZE do .env
        "description": "Equilibrado (RECOMENDADO para Usenet) — slice dinâmico automático",
        "slice_size": None,
        "redundancy": 10,
        "post_size": "50M",
    },
    "safe": {
        "description": "Alta proteção (ideal para arquivos críticos)",
        "slice_size": "5M",
        "redundancy": 20,
        "post_size": "30M",
    },
}

DEFAULT_PROFILE = "balanced"
