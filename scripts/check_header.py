"""Verifica se o header de um artigo está visível no servidor NNTP.

Uso:
    python3 scripts/check_header.py /caminho/para/seu.nzb

Lê as credenciais de ~/.config/upapasta/.env (stdlib apenas, sem python-dotenv).
"""
from __future__ import annotations

import nntplib
import os
import ssl
import sys
import xml.etree.ElementTree as ET

# Importa load_env_file do pacote; funciona tanto com o pacote instalado
# quanto rodando direto da raiz do repositório (python3 scripts/check_header.py).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from upapasta.config import load_env_file


def verify_nntp_header(nzb_path: str) -> None:
    config_path = os.path.expanduser("~/.config/upapasta/.env")
    env = load_env_file(config_path)

    host = env.get("NNTP_HOST")
    port = int(env.get("NNTP_PORT", "119"))
    user = env.get("NNTP_USER")
    password = env.get("NNTP_PASS")
    use_ssl = env.get("NNTP_SSL", "false").lower() == "true"

    if not host:
        print("Erro: NNTP_HOST não encontrado em ~/.config/upapasta/.env")
        sys.exit(1)

    print(f"Conectando a {host}:{port}...")

    tree = ET.parse(nzb_path)
    ns = {"nzb": "http://www.newzbin.com/DTD/2003/nzb"}
    segment = tree.find(".//nzb:segment", ns)
    if segment is None:
        print("Não foi possível encontrar segmentos no NZB.")
        return

    msg_id = segment.text
    print(f"Verificando Message-ID: <{msg_id}>")

    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            server = nntplib.NNTP_SSL(host, port, user=user, password=password, ssl_context=ctx)
        else:
            server = nntplib.NNTP(host, port, user=user, password=password)

        resp, info = server.head(f"<{msg_id}>")
        headers = [line.decode("utf-8", errors="ignore") for line in info.lines]
        subject_line = next(
            (h for h in headers if h.lower().startswith("subject:")),
            "Subject não encontrado",
        )

        print("\n" + "=" * 50)
        print("RESULTADO DO SERVIDOR (O QUE É PÚBLICO):")
        print("=" * 50)
        print(subject_line)
        print("=" * 50)

        server.quit()

    except Exception as e:
        print(f"Erro ao consultar servidor: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        verify_nntp_header(sys.argv[1])
    else:
        print("Uso: python3 scripts/check_header.py /caminho/para/seu.nzb")
