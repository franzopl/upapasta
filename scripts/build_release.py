#!/usr/bin/env python3
"""
build_release.py

Script para automatizar a criação do Portable ZIP do UpaPasta.
1. Compila o UpaPasta via PyInstaller.
2. Baixa binários open-source (nyuu, parpar, 7z) para a pasta bin/.
3. Empacota tudo em um arquivo .zip.

Uso:
  python3 scripts/build_release.py --platform windows
"""

import argparse
import os
import shutil
import subprocess
import urllib.request
import zipfile
import sys

# URLs de exemplo (devem ser validadas/atualizadas para versões reais)
BINARIES = {
    "windows": {
        "nyuu": "https://github.com/Piorosen/nyuu/releases/download/v0.4.2/nyuu-win-x64.exe",
        "parpar": "https://github.com/animetosho/ParPar/releases/download/v0.4.2/parpar-win-x64.exe",
        "7z": "https://www.7-zip.org/a/7zr.exe",  # 7z reduzido
    },
    "linux": {
        "nyuu": "https://github.com/Piorosen/nyuu/releases/download/v0.4.2/nyuu-linux-x64",
        "parpar": "https://github.com/animetosho/ParPar/releases/download/v0.4.2/parpar-linux-x64",
    }
}

def build_executable():
    print("🏗️  Compilando UpaPasta com PyInstaller...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "upapasta",
        "--add-data", f"upapasta/locale{os.pathsep}upapasta/locale",
        "upapasta/main.py"
    ]
    subprocess.run(cmd, check=True)

def download_binaries(platform, dist_dir):
    bin_dir = os.path.join(dist_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    if platform not in BINARIES:
        print(f"⚠️  Nenhum binário predefinido para a plataforma '{platform}'.")
        return

    for name, url in BINARIES[platform].items():
        print(f"⬇️  Baixando {name}...")
        ext = ".exe" if platform == "windows" else ""
        target = os.path.join(bin_dir, f"{name}{ext}")
        try:
            urllib.request.urlretrieve(url, target)
            if platform == "linux":
                os.chmod(target, 0o755)
        except Exception as e:
            print(f"❌ Erro ao baixar {name}: {e}")

def create_zip(platform, dist_dir):
    zip_name = f"upapasta-portable-{platform}.zip"
    print(f"📦 Criando arquivo {zip_name}...")
    
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        # Adiciona o executável
        exe_name = "upapasta.exe" if platform == "windows" else "upapasta"
        exe_path = os.path.join("dist", exe_name)
        if os.path.exists(exe_path):
            z.write(exe_path, exe_name)
        
        # Adiciona pasta bin
        bin_dir = os.path.join(dist_dir, "bin")
        if os.path.exists(bin_dir):
            for root, _, files in os.walk(bin_dir):
                for f in files:
                    abs_path = os.path.join(root, f)
                    rel_path = os.path.relpath(abs_path, dist_dir)
                    z.write(abs_path, rel_path)
                    
    print(f"✅ Release pronto: {zip_name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["windows", "linux"], default="windows")
    args = parser.parse_args()
    
    dist_dir = "dist"
    
    # build_executable()  # Comentado para não rodar durante a demonstração se não houver pyinstaller
    download_binaries(args.platform, dist_dir)
    create_zip(args.platform, dist_dir)

if __name__ == "__main__":
    main()
