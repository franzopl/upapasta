#!/usr/bin/env python3
"""
nzb.py

Utilitários compartilhados para resolução de caminho, tratamento de conflitos
e correção de subjects em arquivos NZB.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from .config import render_template


def resolve_nzb_template(env_vars: dict, is_folder: bool, skip_rar: bool) -> str:
    """Retorna o template NZB_OUT a ser usado."""
    template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT")
    if not template:
        return "{filename}.nzb"
    
    # Se o template aponta para um diretório existente, termina com barra
    # ou não contém o template/extensão esperada, anexar automaticamente {filename}.nzb
    if "{filename}" not in template:
        if os.path.isdir(template) or template.endswith("/") or template.endswith("\\") or not template.lower().endswith(".nzb"):
            return os.path.join(template, "{filename}.nzb")
        
    return template


def resolve_nzb_basename(
    input_path: str,
    is_folder: bool,
    obfuscated_map: dict | None = None,
) -> str:
    """Determina o basename para substituição de {filename} no template NZB_OUT."""
    if obfuscated_map:
        if is_folder:
            obfuscated_basename = os.path.basename(input_path)
            original_name = obfuscated_map.get(obfuscated_basename)
            return original_name if original_name else obfuscated_basename
        else:
            # Valor já é base name sem extensão — não aplicar splitext novamente
            return next(iter(obfuscated_map.values()))

    basename = os.path.basename(input_path)
    if not is_folder:
        basename = os.path.splitext(basename)[0]
        # Volumes RAR: "nome.part01" → "nome"
        if input_path.endswith(".rar") and ".part" in basename:
            basename = basename.rsplit(".part", 1)[0]
    return basename


def resolve_nzb_out(
    input_path: str,
    env_vars: dict,
    is_folder: bool,
    skip_rar: bool,
    working_dir: str,
    obfuscated_map: dict | None = None,
) -> tuple[str, str]:
    """Resolve o caminho de saída do NZB a partir do template e do input.

    Retorna (nzb_out, nzb_out_abs) onde:
    - nzb_out: caminho relativo ou absoluto (passado ao nyuu com -o)
    - nzb_out_abs: caminho absoluto resolvido (para checagens de existência)
    """
    template = resolve_nzb_template(env_vars, is_folder, skip_rar)
    basename = resolve_nzb_basename(input_path, is_folder, obfuscated_map)
    nzb_out = render_template(template, basename)

    if os.path.isabs(nzb_out):
        nzb_out_abs = nzb_out
    else:
        nzb_out_abs = os.path.join(working_dir, nzb_out)

    return nzb_out, nzb_out_abs


def handle_nzb_conflict(
    nzb_out: str,
    nzb_out_abs: str,
    env_vars: dict,
    nzb_overwrite_env: str | None = None,
    working_dir: str | None = None,
) -> tuple[str, str, bool, bool]:
    """Trata colisão com arquivo NZB existente.

    Retorna (nzb_out, nzb_out_abs, nzb_overwrite, ok):
    - nzb_out / nzb_out_abs: caminhos finais (podem ser renomeados)
    - nzb_overwrite: True se o flag -O deve ser passado ao nyuu
    - ok: False quando o modo 'fail' é acionado (operação deve parar)
    """
    nzb_conflict = env_vars.get("NZB_CONFLICT") or os.environ.get("NZB_CONFLICT") or "rename"

    if nzb_overwrite_env is not None:
        nzb_overwrite = nzb_overwrite_env.lower() in ("true", "1", "yes")
    else:
        nzb_overwrite = nzb_conflict == "overwrite"

    if not os.path.exists(nzb_out_abs):
        return nzb_out, nzb_out_abs, nzb_overwrite, True

    if nzb_conflict == "overwrite":
        nzb_overwrite = True
        print(f"Aviso: arquivo NZB já existe: {nzb_out_abs} - sobrescrevendo por solicitação (overwrite)")
    elif nzb_conflict == "fail":
        print(f"Erro: arquivo NZB já existe: {nzb_out_abs}. Parando por configuração 'fail'.")
        return nzb_out, nzb_out_abs, nzb_overwrite, False
    else:  # rename
        base, ext = os.path.splitext(nzb_out_abs)
        counter = 1
        while True:
            candidate = f"{base}-{counter}{ext}"
            if not os.path.exists(candidate):
                break
            counter += 1
        if os.path.isabs(nzb_out):
            nzb_out = candidate
        elif working_dir:
            nzb_out = os.path.relpath(candidate, working_dir)
        else:
            nzb_out = os.path.basename(candidate)
        nzb_out_abs = candidate
        print(f"Aviso: arquivo NZB já existe - usando novo nome: {os.path.basename(candidate)}")

    return nzb_out, nzb_out_abs, nzb_overwrite, True


def inject_nzb_password(nzb_path: str, password: str) -> None:
    """Injeta senha RAR no <head> do NZB para extração automática pelos clientes."""
    try:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        head = root.find(f"{{{ns}}}head") or root.find("head")
        if head is None:
            head = ET.Element(f"{{{ns}}}head")
            root.insert(0, head)

        # Remove senha anterior se existir
        for meta in list(head):
            if meta.get("type") == "password":
                head.remove(meta)

        meta_elem = ET.SubElement(head, f"{{{ns}}}meta")
        meta_elem.set("type", "password")
        meta_elem.text = password

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
    except Exception as e:
        print(f"Aviso: não foi possível injetar senha no NZB: {e}")


import re

def fix_nzb_subjects(
    nzb_path: str,
    file_list: list[str] | None = None,
    folder_name: str | None = None,
    obfuscated_map: dict | None = None,
) -> None:
    """Corrige os subjects no NZB para incluir o caminho relativo do arquivo.
    
    Tenta preservar a estrutura do subject (partes/total, yEnc, etc) substituindo
    apenas o nome do arquivo pelo caminho original (deofuscado).
    """
    try:
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        ns_url = "http://www.newzbin.com/DTD/2003/nzb"
        files = root.findall(f".//{{{ns_url}}}file")
        if not files:
            # Tenta sem namespace como fallback
            files = root.findall(".//file")
        
        print(f"DEBUG fix_nzb_subjects: found {len(files)} files in {os.path.basename(nzb_path)}")
        if obfuscated_map:
            print(f"DEBUG fix_nzb_subjects: obfuscated_map={obfuscated_map}")

        for i, file_elem in enumerate(files):
            old_subject = file_elem.get("subject", "")
            
            # Determina qual nome de arquivo usar para este elemento.
            # Se uma file_list foi fornecida e tem o mesmo tamanho, usamos ela.
            # Caso contrário, tentamos extrair o nome do próprio subject atual.
            current_filename = ""
            if file_list and len(file_list) == len(files):
                current_filename = file_list[i]
            else:
                # Tenta extrair entre aspas ou usa o subject inteiro se for simples
                if '"' in old_subject:
                    m = re.search(r'\"(.*?)\"', old_subject)
                    if m:
                        current_filename = m.group(1)
                else:
                    # Se não tem aspas, assume que o subject pode ser o próprio nome (comum em ofuscados)
                    # mas remove tags típicas se houver
                    current_filename = old_subject.split(' (')[0].split(' [')[0].strip()

            if not current_filename:
                continue

            if current_filename.lower().endswith('.par2'):
                continue

            # Tenta deofuscar
            original_filename = current_filename
            if obfuscated_map:
                if current_filename in obfuscated_map:
                    original_filename = obfuscated_map[current_filename]
                else:
                    # Tenta match por base name (ex: 12345.part01.rar -> 12345)
                    base = current_filename
                    ext_part = ""
                    
                    # Trata .partNN.rar
                    rar_match = re.search(r'(\.part\d+\.rar)$', current_filename, re.IGNORECASE)
                    if rar_match:
                        ext_part = rar_match.group(1)
                        base = current_filename[:-len(ext_part)]
                    else:
                        # Trata extensão simples
                        base, ext_part = os.path.splitext(current_filename)
                    
                    if base in obfuscated_map:
                        original_filename = obfuscated_map[base] + ext_part

            if folder_name:
                final_filename = f"{folder_name}/{original_filename}"
            else:
                final_filename = original_filename
            
            if '"' in old_subject:
                # Substitui o conteúdo entre as aspas duplas
                new_subject = re.sub(r'\"(.*?)\"', f'"{final_filename}"', old_subject)
            else:
                # Se o subject original era apenas o nome, substitui por completo
                if old_subject.strip() == current_filename:
                    new_subject = final_filename
                else:
                    # Tenta substituir a ocorrência do nome no subject
                    new_subject = old_subject.replace(current_filename, final_filename)
                
            file_elem.set("subject", new_subject)

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
        print("NZB corrigido: subjects dos arquivos de dados atualizados.")
    except Exception as e:
        print(f"Aviso: não foi possível corrigir o NZB: {e}")


def fix_season_nzb_subjects(season_nzb_path: str, episode_data: list[tuple[str, str]]) -> None:
    """Garante que cada subject no NZB consolidado da temporada tem o prefixo ep_name/.

    Lê os subjects dos NZBs individuais (já processados) e os mapeia para o nome
    do episódio correspondente. No NZB consolidado, substitui ou adiciona o prefixo
    correto (ex: S01E01/video.mkv) independente do que fix_nzb_subjects fez antes.
    """
    ns_url = "http://www.newzbin.com/DTD/2003/nzb"

    # Mapeia subject → ep_name lendo cada NZB individual
    subject_to_ep: dict[str, str] = {}
    for ep_nzb_path, ep_name in episode_data:
        try:
            ep_root = ET.parse(ep_nzb_path).getroot()
            files = ep_root.findall(f".//{{{ns_url}}}file") or ep_root.findall(".//file")
            for f in files:
                subj = f.get("subject", "")
                if subj:
                    subject_to_ep[subj] = ep_name
        except Exception as e:
            print(f"Aviso: não foi possível ler NZB do episódio '{ep_name}': {e}")

    if not subject_to_ep:
        return

    ET.register_namespace("", ns_url)
    try:
        tree = ET.parse(season_nzb_path)
        root = tree.getroot()
        files = root.findall(f".//{{{ns_url}}}file") or root.findall(".//file")

        for file_elem in files:
            old_subj = file_elem.get("subject", "")
            ep_name = subject_to_ep.get(old_subj)
            if ep_name is None:
                continue

            m = re.search(r'"(.*?)"', old_subj)
            if not m:
                continue

            fname = m.group(1)
            # Remove prefixo de pasta existente (pode ser nome ofuscado ou errado)
            if "/" in fname:
                fname = fname.split("/", 1)[1]

            if not fname or fname.lower().endswith(".par2"):
                continue

            new_fname = f"{ep_name}/{fname}"
            new_subj = re.sub(r'".*?"', f'"{new_fname}"', old_subj, count=1)
            file_elem.set("subject", new_subj)

        tree.write(season_nzb_path, encoding="UTF-8", xml_declaration=True)
        print("NZB da temporada corrigido: subjects atualizados com nomes dos episódios.")
    except Exception as e:
        print(f"Erro ao corrigir subjects do NZB da temporada: {e}")


def merge_nzbs(nzb_paths: list[str], output_path: str) -> bool:
    """Mescla múltiplos arquivos NZB em um único, preservando o head do primeiro."""
    if not nzb_paths:
        return False

    try:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        
        # Usa o primeiro NZB como base para o <head>
        first_tree = ET.parse(nzb_paths[0])
        first_root = first_tree.getroot()
        
        # Coleta todos os elementos <file> dos outros NZBs
        for other_path in nzb_paths[1:]:
            other_tree = ET.parse(other_path)
            other_root = other_tree.getroot()
            
            # Encontra todos os elementos <file> (com ou sem namespace)
            files = other_root.findall(f"{{{ns}}}file") or other_root.findall("file")
            for file_elem in files:
                first_root.append(file_elem)
        
        # Escreve o resultado
        first_tree.write(output_path, encoding="UTF-8", xml_declaration=True)
        return True
    except Exception as e:
        print(f"Erro ao mesclar NZBs: {e}")
        return False
