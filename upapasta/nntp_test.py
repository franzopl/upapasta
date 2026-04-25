"""
nntp_test.py

Utilitário para testar conectividade com servidor NNTP.
"""

from __future__ import annotations

import ssl
import sys

try:
    import nntplib
except ImportError:
    nntplib = None


def test_nntp_connection(
    host: str,
    port: int,
    use_ssl: bool,
    user: str,
    password: str,
    timeout: int = 10,
) -> tuple[bool, str]:
    """Testa conectividade com servidor NNTP.

    Retorna (sucesso: bool, mensagem: str).
    """
    if nntplib is None:
        if sys.version_info >= (3, 14):
            return False, (
                f"❌ nntplib não disponível em Python 3.14+. "
                f"O módulo foi removido da stdlib. "
                f"Use Python 3.13 ou inferior para --test-connection."
            )
        return False, f"❌ nntplib não disponível no seu ambiente."

    try:
        if use_ssl:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            nntp = nntplib.NNTP_SSL(
                host,
                port,
                user=user,
                password=password,
                ssl_context=context,
                timeout=timeout,
            )
        else:
            nntp = nntplib.NNTP(
                host,
                port,
                user=user,
                password=password,
                timeout=timeout,
            )

        nntp.quit()
        return True, f"✅ Conexão bem-sucedida com {host}:{port}"

    except nntplib.NNTPPermanentError as e:
        if "authentication" in str(e).lower() or "login" in str(e).lower():
            return False, f"❌ Erro de autenticação: {e}"
        return False, f"❌ Erro permanente do servidor: {e}"

    except nntplib.NNTPTemporaryError as e:
        return False, f"❌ Erro temporário do servidor: {e}"

    except TimeoutError:
        return False, f"❌ Timeout ao conectar em {host}:{port} (verifique se o servidor está disponível)"

    except ConnectionRefusedError:
        return False, f"❌ Conexão recusada em {host}:{port}"

    except OSError as e:
        if "Name or service not known" in str(e):
            return False, f"❌ Host não resolvível: {host}"
        return False, f"❌ Erro de conexão: {e}"

    except Exception as e:
        return False, f"❌ Erro inesperado: {e}"
