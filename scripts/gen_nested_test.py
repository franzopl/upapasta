#!/usr/bin/env python3
import os
import sys
import random
import string
import shutil
import subprocess
from pathlib import Path

def generate_random_name(length=12):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_nested_structure(root_path, levels=5, dirs_per_level=2, files_per_dir=3):
    """Cria uma estrutura de pastas aninhadas com arquivos aleatórios."""
    root = Path(root_path)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    current_level_dirs = [root]
    
    print(f"--- Gerando estrutura em: {root_path} ---")
    
    for level in range(1, levels + 1):
        next_level_dirs = []
        for d in current_level_dirs:
            # Criar arquivos no diretório atual
            for i in range(files_per_dir):
                fname = f"file_L{level}_{i}_{generate_random_name(6)}.bin"
                fpath = d / fname
                # Conteúdo aleatório para garantir hashes únicos
                fpath.write_bytes(os.urandom(1024 * 10)) # 10KB
            
            # Criar subdiretórios (exceto no último nível)
            if level < levels:
                for i in range(dirs_per_level):
                    dname = f"folder_L{level}_{i}_{generate_random_name(4)}"
                    dpath = d / dname
                    dpath.mkdir()
                    next_level_dirs.append(dpath)
        
        current_level_dirs = next_level_dirs
    
    print(f"Estrutura de {levels} níveis criada com sucesso.")

def run_upapasta_test(target_path):
    """Executa upapasta com --strong-obfuscate em modo dry-run."""
    print(f"\n--- Testando upapasta --strong-obfuscate em: {target_path} ---")
    
    # Usaremos --dry-run para não tentar fazer upload real
    # Mas precisamos de um comando que dispare a ofuscação
    cmd = [
        sys.executable, "-m", "upapasta.main",
        str(target_path),
        "--strong-obfuscate",
        "--dry-run",
        "--skip-rar" # Para testar a pasta diretamente
    ]
    
    print(f"Executando: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Erro ao executar upapasta:")
        print(result.stderr)
        return False
    
    print("Saída do upapasta:")
    print(result.stdout)
    return True

if __name__ == "__main__":
    TEST_DIR = "test_nested_strong"
    create_nested_structure(TEST_DIR, levels=5)
    
    print("\nPronto! A pasta '" + TEST_DIR + "' foi criada.")
    print("Você pode testar manualmente com:")
    print(f"python3 -m upapasta.main {TEST_DIR} --strong-obfuscate --skip-rar")
    print("\nOu deixe que eu tente rodar um teste básico agora...")
    
    # run_upapasta_test(TEST_DIR)
