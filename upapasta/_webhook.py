"""
_webhook.py

Envio de notificações pós-upload via webhook HTTP (Discord / Slack / genérico).
Requer apenas stdlib (urllib). Falhas são não-fatais — só loggam um aviso.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger("upapasta")

_TIMEOUT = 10  # segundos


def _build_payload(
    url: str,
    nome: str,
    tamanho_bytes: Optional[int],
    grupo: Optional[str],
    categoria: Optional[str],
) -> dict[str, object]:
    gb = f"{tamanho_bytes / (1024**3):.2f} GB" if tamanho_bytes else "?"
    grupo_str = f" → {grupo}" if grupo else ""
    cat_str = f" [{categoria}]" if categoria else ""
    msg = f"✅ Upload concluído: {nome}{cat_str} ({gb}){grupo_str}"

    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return {"content": msg}

    if "hooks.slack.com" in url:
        return {"text": msg}

    # Telegram bot API: POST body é o JSON completo com text + parse_mode
    if "api.telegram.org" in url:
        return {"text": msg}

    # Payload genérico rico
    return {
        "message": msg,
        "nome": nome,
        "tamanho_bytes": tamanho_bytes,
        "grupo": grupo,
        "categoria": categoria,
    }


def send_webhook(
    url: str,
    nome: str,
    *,
    tamanho_bytes: Optional[int] = None,
    grupo: Optional[str] = None,
    categoria: Optional[str] = None,
) -> None:
    """Envia notificação POST JSON ao webhook configurado. Não lança exceções."""
    payload = _build_payload(url, nome, tamanho_bytes, grupo, categoria)
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT):
            pass
        logger.debug("Webhook enviado para %s", url)
    except urllib.error.HTTPError as e:
        logger.warning("Webhook HTTP %s: %s", e.code, e.reason)
    except Exception as e:
        logger.warning("Webhook falhou: %s", e)
