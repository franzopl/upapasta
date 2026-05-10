#!/usr/bin/env python3
"""
build_release.py

Script para automatizar a criação do Portable ZIP do UpaPasta.
"""

import argparse
import os
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import tempfile
import sys
import lzma

# URLs validadas via API do GitHub
BINARIES = {
    "windows": {
        "nyuu": "https://github.com/animetosho/Nyuu/releases/download/v0.4.2/nyuu-v0.4.2-win32.7z",
        "parpar": "https://github.com/animetosho/ParPar/releases/download/v0.4.5/parpar-v0.4.5-win64.7z",
        "7z": "https://www.7-zip.org/a/7zr.exe",
    },
    "linux": {
        "nyuu": "https://github.com/animetosho/Nyuu/releases/download/v0.4.2/nyuu-v0.4.2-linux-amd64.tar.xz",
        "parpar": "https://github.com/animetosho/ParPar/releases/download/v0.4.5/parpar-v0.4.5-linux-static-amd64.xz",
    }
}

def build_executable():
    print("🏗️  Compilando UpaPasta com PyInstaller...")
    if shutil.which("pyinstaller") is None:
        print("❌ Erro: pyinstaller não encontrado.")
        return False
    cmd = [
        "pyinstaller", "--onefile", "--name", "upapasta",
        "--add-data", f"upapasta/locale{os.pathsep}upapasta/locale",
        "upapasta/main.py"
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def extract_7z_with_python(archive_path, extract_dir, name):
    """Tenta extrair .7z usando py7zr se disponível, senão avisa."""
    try:
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            z.extractall(path=extract_dir)
            return True
    except ImportError:
        # Fallback: se tivermos 7z no sistema, usamos ele
        exe_7z = shutil.which("7z") or shutil.which("7za")
        if exe_7z:
            subprocess.run([exe_7z, "x", archive_path, f"-o{extract_dir}", "-y"], check=True)
            return True
        else:
            print(f"⚠️  Aviso: Não foi possível extrair {name} (.7z). Instale 'py7zr' ou 'p7zip'.")
            return False

def download_and_extract(name, url, platform, bin_dir):
    print(f"⬇️  Baixando {name}...")
    temp_dir = tempfile.mkdtemp()
    local_file = os.path.join(temp_dir, os.path.basename(url))
    
    try:
        urllib.request.urlretrieve(url, local_file)
        
        if local_file.endswith(".7z"):
            if extract_7z_with_python(local_file, temp_dir, name):
                # Procura o binário nas pastas extraídas
                ext = ".exe" if platform == "windows" else ""
                target_name = f"{name}{ext}"
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f.lower() == target_name.lower() or f.lower() == f"{name}.exe".lower():
                            shutil.move(os.path.join(root, f), os.path.join(bin_dir, target_name))
                            break
        
        elif local_file.endswith(".tar.xz"):
            with tarfile.open(local_file, "r:xz") as tar:
                tar.extractall(path=temp_dir)
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f == name or f == f"{name}-v0.4.2-linux-amd64": # Caso nyuu
                            final_path = os.path.join(bin_dir, name)
                            shutil.move(os.path.join(root, f), final_path)
                            os.chmod(final_path, 0o755)
                            break
                            
        elif local_file.endswith(".xz") and not local_file.endswith(".tar.xz"):
            # Caso do parpar linux que é o binário puro comprimido em xz
            final_path = os.path.join(bin_dir, name)
            with lzma.open(local_file, "rb") as f_in:
                with open(final_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.chmod(final_path, 0o755)

        elif local_file.endswith(".exe"):
            shutil.copy2(local_file, os.path.join(bin_dir, f"{name}.exe"))
            
        print(f"✅ {name} processado com sucesso.")
        
    except Exception as e:
        print(f"❌ Erro ao processar {name}: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def create_zip(platform, dist_dir):
    zip_name = f"upapasta-portable-{platform}.zip"
    print(f"📦 Criando arquivo {zip_name}...")
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        exe_name = "upapasta.exe" if platform == "windows" else "upapasta"
        exe_path = os.path.join("dist", exe_name)
        if os.path.exists(exe_path):
            z.write(exe_path, exe_name)
        
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
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    
    dist_dir = "dist"
    if not args.skip_build:
        build_executable()
            
    bin_dir = os.path.join(dist_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    if args.platform in BINARIES:
        for name, url in BINARIES[args.platform].items():
            download_and_extract(name, url, args.platform, bin_dir)
            
    create_zip(args.platform, dist_dir)

if __name__ == "__main__":
    main()
