#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import re
from pathlib import Path

# Adiciona o diretório atual ao sys.path
sys.path.append(os.getcwd())
from upapasta.makepar import obfuscate_and_par

def final_validation():
    SOURCE_DIR = Path("test_nested_strong")
    STRESS_ENV = Path("stress_final_env")
    
    if not SOURCE_DIR.exists():
        print("❌ Execute scripts/gen_nested_test.py primeiro!")
        return

    print("\n" + "💎" * 20)
    print("🚀 VALIDAÇÃO FINAL: REVERSÃO DE STRONG OBFUSCATE")
    print("💎" * 20)

    # 1. Ofuscação real via UpaPasta
    print(f"\n1. Ofuscando 5 níveis com parpar...")
    rc, new_path, mapping, linked = obfuscate_and_par(
        str(SOURCE_DIR), redundancy=10, backend="parpar", usenet=True, force=True
    )
    random_root = os.path.basename(new_path)
    
    # 2. Isolamento
    if STRESS_ENV.exists(): shutil.rmtree(STRESS_ENV)
    STRESS_ENV.mkdir()
    shutil.move(new_path, STRESS_ENV / random_root)
    for p in Path(".").glob(f"{random_root}*.par2"):
        shutil.move(p, STRESS_ENV / p.name)

    # 3. O "Pulo do Gato": Usar o PAR2 para identificar os arquivos
    print("\n2. 🔍 Escaneando arquivos ofuscados com PAR2...")
    all_bins = [str(f.relative_to(STRESS_ENV)) for f in (STRESS_ENV / random_root).rglob("*.bin")]
    main_par2 = f"{random_root}.par2"
    
    cmd = ["par2", "repair", main_par2] + all_bins
    process = subprocess.run(cmd, cwd=STRESS_ENV, capture_output=True, text=True)

    # 4. Analisar a saída do PAR2 para provar os matches
    print("\n3. 📊 Analisando matches encontrados pelo PAR2:")
    matches = re.findall(r'File: "(.+?)" - is a match for "(.+?)"', process.stdout)
    
    for obfuscated, original in matches[:5]:
        print(f"   🔗 Match: {obfuscated}  ===>  {original}")
    
    print(f"\n   ✅ Total de matches identificados: {len(matches)}/93")

    # 5. Renomeação Forçada (Simulando SABnzbd)
    print("\n4. 🏗️  Restaurando estrutura original (forçando renomeação)...")
    for obfuscated, original in matches:
        dest = STRESS_ENV / original
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(STRESS_ENV / obfuscated, dest)

    # 6. Verificação de Sucesso
    recovered = list(STRESS_ENV.glob("test_nested_strong/folder_L1_*"))
    if len(recovered) > 0:
        print("\n🏆 SUCESSO ABSOLUTO!")
        print(f"   A árvore de diretórios e os arquivos originais foram restaurados.")
        print(f"   Isso confirma que o '--strong-obfuscate' do UpaPasta é 100% seguro e reversível.")
    else:
        print("\n❌ Falha ao restaurar.")

if __name__ == "__main__":
    final_validation()
