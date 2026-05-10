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

# URLs EXATAS validadas via API do GitHub
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

def extract_7z(archive_path, extract_dir):
    """Extrai .7z usando o binário 7z do sistema ou py7zr."""
    # Tenta usar o binário do sistema primeiro (mais rápido/confiável)
    exe_7z = shutil.which("7z") or shutil.which("7za")
    if exe_7z:
        try:
            subprocess.run([exe_7z, "x", archive_path, f"-o{extract_dir}", "-y"], check=True, stdout=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            pass
            
    # Fallback para py7zr
    try:
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            z.extractall(path=extract_dir)
            return True
    except ImportError:
        print(f"⚠️  Erro: Para extrair .7z sem o comando '7z' no sistema, instale 'pip install py7zr'.")
        return False

def download_file(url, local_path):
    """Downloads a file using curl, wget, or urllib as a fallback."""
    print(f"   Download: {url}")
    if shutil.which("curl"):
        try:
            subprocess.run(["curl", "-Lk", "--connect-timeout", "30", "--retry", "5", "-o", local_path, url], check=True)
            return True
        except subprocess.CalledProcessError:
            pass
    if shutil.which("wget"):
        try:
            subprocess.run(["wget", "-q", "--timeout=30", "--tries=5", "-O", local_path, url], check=True)
            return True
        except subprocess.CalledProcessError:
            pass
    try:
        urllib.request.urlretrieve(url, local_path)
        return True
    except Exception as e:
        print(f"      ❌ Erro no download: {e}")
        return False

def download_and_extract(name, url, platform, bin_dir):
    print(f"⬇️  Baixando {name}...")
    temp_dir = tempfile.mkdtemp()
    local_file = os.path.join(temp_dir, os.path.basename(url))
    
    if not download_file(url, local_file):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    try:
        if local_file.endswith(".7z"):
            if extract_7z(local_file, temp_dir):
                ext = ".exe" if platform == "windows" else ""
                target_name = f"{name}{ext}"
                found = False
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f.lower() in (target_name.lower(), f"{name}.exe".lower(), name.lower()):
                            # Evita mover diretórios ou arquivos irrelevantes
                            src = os.path.join(root, f)
                            dst = os.path.join(bin_dir, target_name)
                            if os.path.exists(dst): os.remove(dst)
                            shutil.move(src, dst)
                            found = True
                            break
                    if found: break
        
        elif local_file.endswith((".tar.gz", ".tar.xz")):
            mode = "r:gz" if local_file.endswith(".tar.gz") else "r:xz"
            with tarfile.open(local_file, mode) as tar:
                tar.extractall(path=temp_dir)
                found = False
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f == name or f.startswith(f"{name}-v") or f.startswith(f"{name}-0."):
                            final_path = os.path.join(bin_dir, name)
                            if os.path.exists(final_path): os.remove(final_path)
                            shutil.move(os.path.join(root, f), final_path)
                            os.chmod(final_path, 0o755)
                            found = True
                            break
                    if found: break
                            
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
