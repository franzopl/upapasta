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


def get_app_data_dir() -> str:
    """Retorna o diretório de dados do usuário para o UpaPasta."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(base, "upapasta")
    return os.path.expanduser("~/.config/upapasta")


def get_tool_path(tool_name: str) -> str | None:
    """
    Localiza o caminho de um binário.
    Prioridade:
    1. Pasta bin/ relativa ao executável/script (Modo Portable).
    2. Pasta bin/ no diretório de trabalho atual (CWD).
    3. Pasta bin/ no diretório de dados do usuário (Config/AppData).
    4. PATH do sistema.
    """
    # No Windows, garante que a extensão .exe seja considerada na busca local
    if sys.platform == "win32" and not tool_name.lower().endswith(".exe"):
        executable_name = f"{tool_name}.exe"
    else:
        executable_name = tool_name

    search_dirs = [
        os.path.join(get_base_dir(), "bin"),
        os.path.join(os.getcwd(), "bin"),
        os.path.join(get_app_data_dir(), "bin"),
    ]

    for bin_dir in search_dirs:
        local_bin = os.path.join(bin_dir, executable_name)
        if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
            return local_bin

    # Fallback para o PATH do sistema
    # No Windows, shutil.which retorna .exe, .cmd, .bat dependendo do PATHEXT.
    # Se chegamos aqui, preferimos o .exe se disponível no PATH para evitar o erro do .cmd (Node)
    if sys.platform == "win32" and not tool_name.lower().endswith(".exe"):
        path_exe = shutil.which(f"{tool_name}.exe")
        if path_exe:
            return path_exe

    return shutil.which(tool_name)


def download_tool(tool_name: str) -> str | None:
    """
    Tenta baixar um binário automaticamente.
    """
    if tool_name.lower() != "rar":
        return None

    print(f"\n⬇️  Baixando '{tool_name}' automaticamente...")
    # Para o auto-download do usuário via pip, preferimos salvar na pasta de dados do usuário
    bin_dir = os.path.join(get_app_data_dir(), "bin")
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
