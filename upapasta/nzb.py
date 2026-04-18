#!/usr/bin/env python3
"""
nzb.py

Utilitários compartilhados para resolução de caminho, tratamento de conflitos
e correção de subjects em arquivos NZB.
"""

import os
import xml.etree.ElementTree as ET


def resolve_nzb_template(env_vars: dict, is_folder: bool, skip_rar: bool) -> str:
    """Retorna o template NZB_OUT a ser usado."""
    template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT")
    if not template:
        return "{filename}.nzb"
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
            original_name = next(iter(obfuscated_map.values()))
            return os.path.splitext(os.path.basename(original_name))[0]

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
    nzb_out = template.replace("{filename}", basename)

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


def fix_nzb_subjects(nzb_path: str, file_list: list[str], folder_name: str | None = None) -> None:
    """Corrige os subjects no NZB para incluir o caminho relativo do arquivo."""
    try:
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        files = root.findall(".//{http://www.newzbin.com/DTD/2003/nzb}file")

        if len(files) == len(file_list):
            for i, file_elem in enumerate(files):
                filename = file_list[i]
                if not filename.lower().endswith('.par2'):
                    if folder_name and '/' not in filename:
                        new_subject = f"{folder_name}/{filename}"
                    else:
                        new_subject = filename
                    file_elem.set("subject", new_subject)

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
        print("NZB corrigido: subjects dos arquivos de dados atualizados para preservar estrutura.")
    except Exception as e:
        print(f"Aviso: não foi possível corrigir o NZB: {e}")
