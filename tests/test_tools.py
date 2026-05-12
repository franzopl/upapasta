"""
test_tools.py — Testes para tool discovery e management.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from upapasta.tools import download_tool, get_app_data_dir, get_base_dir, get_tool_path


class TestGetBaseDir:
    """Testes para get_base_dir()."""

    def test_frozen_executable(self):
        """Quando rodando como executável PyInstaller."""
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", "/path/to/app"):
                result = get_base_dir()
                assert result == "/path/to"

    def test_script_mode(self):
        """Quando rodando como script Python."""
        result = get_base_dir()
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetAppDataDir:
    """Testes para get_app_data_dir()."""

    def test_windows_with_appdata(self):
        """Windows com APPDATA setada."""
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "C:\\Users\\user\\AppData\\Roaming"}):
                result = get_app_data_dir()
                assert "upapasta" in result
                assert "AppData" in result or "appdata" in result.lower()

    def test_windows_without_appdata(self):
        """Windows sem APPDATA (fallback para ~)."""
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {}, clear=True):
                result = get_app_data_dir()
                assert "upapasta" in result

    def test_linux(self):
        """Linux usa ~/.config/upapasta."""
        with patch.object(sys, "platform", "linux"):
            result = get_app_data_dir()
            assert ".config" in result or "config" in result
            assert "upapasta" in result


class TestGetToolPath:
    """Testes para get_tool_path()."""

    def test_tool_not_found(self):
        """Tool não encontrada retorna None."""
        with patch("upapasta.tools.shutil.which", return_value=None):
            result = get_tool_path("nonexistent_tool_xyz")
            assert result is None

    def test_tool_found_in_system_path(self):
        """Tool encontrada no PATH do sistema."""
        with patch("upapasta.tools.os.path.exists", return_value=False):
            with patch("upapasta.tools.shutil.which") as mock_which:
                mock_which.return_value = "/usr/bin/nyuu"
                result = get_tool_path("nyuu")
                assert result == "/usr/bin/nyuu"

    def test_tool_path_windows_exe_added(self):
        """Windows: adiciona .exe ao procurar no PATH."""
        with patch.object(sys, "platform", "win32"):
            with patch("upapasta.tools.shutil.which") as mock_which:
                mock_which.return_value = "C:\\Tools\\rar.exe"
                result = get_tool_path("rar")
                assert result == "C:\\Tools\\rar.exe"
                # Deve ter procurado por rar.exe primeiro
                assert any("rar.exe" in str(call) for call in mock_which.call_args_list)

    def test_tool_in_local_bin_dir(self):
        """Tool encontrada em bin/ local."""
        with patch("upapasta.tools.os.path.exists") as mock_exists:
            with patch("upapasta.tools.os.access") as mock_access:
                # bin/nyuu existe
                mock_exists.return_value = True
                mock_access.return_value = True

                result = get_tool_path("nyuu")
                assert result is not None
                assert "bin" in result
                assert "nyuu" in result


class TestDownloadTool:
    """Testes para download_tool()."""

    def test_download_tool_not_supported(self):
        """Tool que não é RAR retorna None."""
        result = download_tool("nyuu")
        assert result is None

    def test_download_rar_disabled_non_windows_linux(self):
        """download_tool para RAR em plataforma não suportada retorna None."""
        with patch.object(sys, "platform", "darwin"):
            result = download_tool("rar")
            assert result is None

    def test_download_rar_function_exists(self):
        """Função download_tool existe e é chamável."""
        assert callable(download_tool)
