"""
tools.py

Gerenciamento centralizado de binários externos (nyuu, parpar, 7z, rar, etc.).
Suporta busca em pasta bin/ local para portabilidade e futuramente auto-download.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile


def get_base_dir() -> str:
    """Retorna a pasta base onde o binário ou script está localizado."""
    if getattr(sys, "frozen", False):
        # Rodando como executável compilado (PyInstaller)
        return os.path.dirname(sys.executable)
    # Rodando como script Python: upapasta/tools.py -> upapasta/ -> root/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_tool_path(tool_name: str) -> str | None:
    """
    Localiza o caminho de um binário.
    1. Verifica na pasta bin/ local.
    2. Verifica no PATH do sistema.
    """
    # No Windows, garante que a extensão .exe seja considerada na busca local
    if sys.platform == "win32" and not tool_name.lower().endswith(".exe"):
        executable_name = f"{tool_name}.exe"
    else:
        executable_name = tool_name

    base_dir = get_base_dir()
    local_bin = os.path.join(base_dir, "bin", executable_name)

    if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin

    # Fallback para o PATH do sistema
    return shutil.which(tool_name)


def download_tool(tool_name: str) -> str | None:
    """
    Tenta baixar um binário automaticamente.
    Atualmente suporta apenas 'rar' no Windows/Linux como demonstração.
    """
    if tool_name.lower() != "rar":
        return None

    print(f"\n⬇️  Baixando '{tool_name}' automaticamente...")
    base_dir = get_base_dir()
    bin_dir = os.path.join(base_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    try:
        if sys.platform == "win32":
            # Baixa o RAR para Windows
            url = "https://www.rarlab.com/rar/rarwin-x64-701.zip"
            local_zip = os.path.join(tempfile.gettempdir(), "rar.zip")
            urllib.request.urlretrieve(url, local_zip)

            with zipfile.ZipFile(local_zip, "r") as zip_ref:
                # Extrai apenas o rar.exe
                zip_ref.extract("rar/rar.exe", tempfile.gettempdir())
                shutil.move(
                    os.path.join(tempfile.gettempdir(), "rar", "rar.exe"),
                    os.path.join(bin_dir, "rar.exe"),
                )

            os.remove(local_zip)
            return os.path.join(bin_dir, "rar.exe")

        elif sys.platform == "linux":
            # Baixa o RAR para Linux
            url = "https://www.rarlab.com/rar/rarlinux-x64-701.tar.gz"
            local_tgz = os.path.join(tempfile.gettempdir(), "rar.tar.gz")
            urllib.request.urlretrieve(url, local_tgz)

            import tarfile

            with tarfile.open(local_tgz, "r:gz") as tar:
                tar.extract("rar/rar", tempfile.gettempdir())
                shutil.move(
                    os.path.join(tempfile.gettempdir(), "rar", "rar"),
                    os.path.join(bin_dir, "rar"),
                )

            os.remove(local_tgz)
            os.chmod(os.path.join(bin_dir, "rar"), 0o755)
            return os.path.join(bin_dir, "rar")

    except Exception as e:
        print(f"❌ Falha ao baixar '{tool_name}': {e}")

    return None
