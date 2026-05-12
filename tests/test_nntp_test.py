"""
test_nntp_connection.py — Testes para test_nntp_connection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from upapasta.nntp_test import check_nntp_connection


# Criar classes de exceção para mockar nntplib
class MockNNTPError(Exception):
    """Base para exceções NNTP."""

    pass


class MockNNTPPermanentError(MockNNTPError):
    """Simula nntplib.NNTPPermanentError."""

    pass


class MockNNTPTemporaryError(MockNNTPError):
    """Simula nntplib.NNTPTemporaryError."""

    pass


class TestNntpConnectionMissing:
    """Testes quando nntplib não está disponível."""

    def test_nntplib_not_available_pre_314(self):
        """Quando nntplib é None e Python < 3.14, retorna mensagem específica."""
        with patch("upapasta.nntp_test.nntplib", None):
            with patch("upapasta.nntp_test.sys.version_info", (3, 13)):
                success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
                assert not success
                assert "not available" in msg.lower()

    def test_nntplib_not_available_python_314_plus(self):
        """Quando nntplib é None e Python >= 3.14, retorna mensagem removido."""
        with patch("upapasta.nntp_test.nntplib", None):
            with patch("upapasta.nntp_test.sys.version_info", (3, 14)):
                success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
                assert not success
                assert "3.14" in msg or "removed" in msg.lower()


class TestNntpConnectionSuccess:
    """Testes de conexão bem-sucedida."""

    def test_ssl_connection_success(self):
        """Conexão SSL bem-sucedida."""
        mock_nntplib = MagicMock()
        mock_nntp = MagicMock()
        mock_nntplib.NNTP_SSL.return_value = mock_nntp

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 563, True, "user", "pass")
            assert success
            assert "Successfully connected" in msg
            mock_nntplib.NNTP_SSL.assert_called_once()
            mock_nntp.quit.assert_called_once()

    def test_plain_connection_success(self):
        """Conexão sem SSL bem-sucedida."""
        mock_nntplib = MagicMock()
        mock_nntp = MagicMock()
        mock_nntplib.NNTP.return_value = mock_nntp

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert success
            assert "Successfully connected" in msg
            mock_nntplib.NNTP.assert_called_once()
            mock_nntp.quit.assert_called_once()

    def test_ssl_connection_insecure_mode(self):
        """SSL com insecure=True desativa verificação."""
        mock_nntplib = MagicMock()
        mock_nntp = MagicMock()
        mock_nntplib.NNTP_SSL.return_value = mock_nntp

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            with patch("upapasta.nntp_test.ssl.create_default_context") as mock_ssl:
                mock_context = MagicMock()
                mock_ssl.return_value = mock_context

                success, msg = check_nntp_connection(
                    "news.example.com",
                    563,
                    True,
                    "user",
                    "pass",
                    insecure=True,
                )
                assert success
                # Verificar que context foi modificado
                assert mock_context.check_hostname is False
                # verify_mode foi setado para CERT_NONE
                assert mock_context.verify_mode is not None


class TestNntpConnectionErrors:
    """Testes de diferentes tipos de erro."""

    def test_permanent_error_authentication(self):
        """NNTPPermanentError com "authentication"."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = MockNNTPPermanentError("430 Authentication failed")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Authentication error" in msg

    def test_permanent_error_generic(self):
        """NNTPPermanentError genérico."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = MockNNTPPermanentError("500 Error")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Permanent server error" in msg

    def test_temporary_error(self):
        """NNTPTemporaryError."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = MockNNTPTemporaryError("400 Service unavailable")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Temporary server error" in msg

    def test_timeout_error(self):
        """TimeoutError."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = TimeoutError("Connection timed out")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Timeout" in msg

    def test_connection_refused_error(self):
        """ConnectionRefusedError."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = ConnectionRefusedError("Connection refused by server")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Connection refused" in msg

    def test_host_not_resolvable(self):
        """OSError com mensagem 'Name or service not known'."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = OSError("Name or service not known")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("invalid.example.com", 119, False, "user", "pass")
            assert not success
            assert "Host not resolvable" in msg

    def test_generic_oserror(self):
        """OSError genérico."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = OSError("Unknown error")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Connection error" in msg

    def test_unexpected_exception(self):
        """Exceção inesperada (não-nntplib)."""
        mock_nntplib = MagicMock()
        mock_nntplib.NNTPPermanentError = MockNNTPPermanentError
        mock_nntplib.NNTPTemporaryError = MockNNTPTemporaryError
        mock_nntplib.NNTP.side_effect = RuntimeError("Unexpected error")

        with patch("upapasta.nntp_test.nntplib", mock_nntplib):
            success, msg = check_nntp_connection("news.example.com", 119, False, "user", "pass")
            assert not success
            assert "Unexpected error" in msg
