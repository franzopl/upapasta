"""
nntp_test.py

Utilitário para testar conectividade com servidor NNTP.
"""

from __future__ import annotations

import ssl
import sys
from typing import Any

from .i18n import _

try:
    import nntplib
except ImportError:
    nntplib = None  # type: ignore[assignment]


def test_nntp_connection(
    host: str,
    port: int,
    use_ssl: bool,
    user: str,
    password: str,
    timeout: int = 10,
    insecure: bool = False,
) -> tuple[bool, str]:
    """Testa conectividade com servidor NNTP.

    Por padrão verifica o certificado SSL via CA bundle do sistema.
    Passe insecure=True para desativar a verificação (apenas para testes).

    Retorna (sucesso: bool, mensagem: str).
    """
    if nntplib is None:
        if sys.version_info >= (3, 14):
            return False, _(
                "❌ nntplib not available in Python 3.14+. "
                "The module was removed from stdlib. "
                "Use Python 3.13 or lower for --test-connection."
            )
        return False, _("❌ nntplib not available in your environment.")

    try:
        nntp: Any = None  # noqa: F841
        if use_ssl:
            context = ssl.create_default_context()
            if insecure:
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
        return True, _("✅ Successfully connected to {host}:{port}").format(host=host, port=port)

    except nntplib.NNTPPermanentError as e:
        if "authentication" in str(e).lower() or "login" in str(e).lower():
            return False, _("❌ Authentication error: {error}").format(error=e)
        return False, _("❌ Permanent server error: {error}").format(error=e)

    except nntplib.NNTPTemporaryError as e:
        return False, _("❌ Temporary server error: {error}").format(error=e)

    except TimeoutError:
        return False, _(
            "❌ Timeout connecting to {host}:{port} (check if server is available)"
        ).format(host=host, port=port)

    except ConnectionRefusedError:
        return False, _("❌ Connection refused at {host}:{port}").format(host=host, port=port)

    except OSError as e:
        if "Name or service not known" in str(e):
            return False, _("❌ Host not resolvable: {host}").format(host=host)
        return False, _("❌ Connection error: {error}").format(error=e)

    except Exception as e:
        return False, _("❌ Unexpected error: {error}").format(error=e)
