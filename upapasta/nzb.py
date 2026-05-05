#!/usr/bin/env python3
"""
nzb.py

Utilitários compartilhados para resolução de caminho, tratamento de conflitos
e correção de subjects em arquivos NZB.
"""

from __future__ import annotations

import os
import re
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
            val = next(iter(obfuscated_map.values()))
            return val if isinstance(val, str) else ""

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


def _parse_subject(subject: str) -> tuple[str, str, str]:
    """Decompõe um subject Usenet em (prefixo, nome_arquivo, sufixo).

    Suporta os formatos mais comuns gerados por nyuu e outros posters:
      - "filename.ext" yEnc (N/M) [size]
      - [tag] "filename.ext" yEnc (N/M)
      - filename.ext yEnc (N/M)
      - filename.ext (N/M)
      - filename.ext           (sem indicador de parte)

    Retorna (prefixo, nome_arquivo, sufixo). Se não for possível isolar o nome
    do arquivo, retorna ("", subject, "").
    """
    # Caso 1: nome entre aspas duplas — formato canônico nyuu/NewsPost
    m = re.match(r'^(.*?)"([^"]+)"(.*)$', subject, re.DOTALL)
    if m:
        return m.group(1), m.group(2), m.group(3)

    # Caso 2: sem aspas — tenta localizar indicador de parte (N/M) ou yEnc
    # Padrão: <texto_opcional> <nome_arquivo> <yEnc> <(N/M)> <[tamanho]>
    # O nome do arquivo é o token imediatamente antes de "yEnc" ou de "(N/M)"
    m_yenc = re.search(r'^(.*?)(\s+yEnc\s+\(\d+/\d+\).*)$', subject)
    if m_yenc:
        pre = m_yenc.group(1)
        suffix = m_yenc.group(2)
        # O último token de `pre` é o nome do arquivo
        idx = pre.rfind(' ')
        if idx >= 0:
            return pre[:idx + 1], pre[idx + 1:], suffix
        return '', pre, suffix

    m_part = re.search(r'^(.*?)(\s*\(\d+/\d+\).*)$', subject)
    if m_part:
        pre = m_part.group(1)
        suffix = m_part.group(2)
        idx = pre.rfind(' ')
        if idx >= 0:
            return pre[:idx + 1], pre[idx + 1:], suffix
        return '', pre, suffix

    # Caso 3: subject é apenas o nome do arquivo (sem indicadores)
    return '', subject, ''


def _deobfuscate_filename(
    current_filename: str,
    obfuscated_map: dict,
) -> str:
    """Resolve o nome original a partir do mapa de ofuscação.

    Trata extensões compostas (.part01.rar, .vol00+01.par2, .par2) e simples.
    Devolve current_filename se não encontrar mapeamento.
    """
    if current_filename in obfuscated_map:
        return obfuscated_map[current_filename]

    # Extensões compostas: .partNN.rar e .volNN+MM.par2 / .par2
    for pattern in (
        r'(\.part\d+\.rar)$',
        r'(\.vol\d+\+\d+\.par2)$',
        r'(\.par2)$',
    ):
        m = re.search(pattern, current_filename, re.IGNORECASE)
        if m:
            ext = m.group(1)
            base = current_filename[: -len(ext)]
            if base in obfuscated_map:
                return obfuscated_map[base] + ext
            break
    else:
        # Extensão simples
        base, ext = os.path.splitext(current_filename)
        if base in obfuscated_map:
            return obfuscated_map[base] + ext

    return current_filename


def fix_nzb_subjects(
    nzb_path: str,
    file_list: list[str] | None = None,
    folder_name: str | None = None,
    obfuscated_map: dict | None = None,
    strong_obfuscate: bool = False,
) -> None:
    """Corrige os subjects no NZB para incluir o caminho relativo do arquivo.

    Usa _parse_subject para decompor cada subject em (prefixo, nome, sufixo),
    preservando indicadores de parte (N/M), yEnc e demais metadados.

    Se strong_obfuscate=True, mantém os nomes aleatórios (máxima privacidade).
    """
    try:
        ns_url = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns_url)
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        files = root.findall(f".//{{{ns_url}}}file")
        if not files:
            files = root.findall(".//file")

        from_file_list = bool(file_list and len(file_list) == len(files))
        for i, file_elem in enumerate(files):
            old_subject = file_elem.get("subject", "")

            if from_file_list:
                # file_list é autoritativo: o subject pode ser placeholder gerado pelo uploader
                current_filename = file_list[i]  # type: ignore[index]
                prefix, suffix = "", ""
            else:
                prefix, current_filename, suffix = _parse_subject(old_subject)

            if not current_filename:
                continue

            # Deofuscação (pulada quando strong_obfuscate ou sem mapa)
            if strong_obfuscate or not obfuscated_map:
                original_filename = current_filename
            else:
                original_filename = _deobfuscate_filename(current_filename, obfuscated_map)

            if strong_obfuscate:
                final_filename = current_filename
            elif folder_name:
                final_filename = f"{folder_name}/{original_filename}"
            else:
                final_filename = original_filename

            # Reconstrói o subject preservando prefixo e sufixo
            quoted = '"' in old_subject
            if quoted:
                new_subject = f'{prefix}"{final_filename}"{suffix}'
            else:
                new_subject = f'{prefix}{final_filename}{suffix}'

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
            episode_name: str | None = subject_to_ep.get(old_subj)
            if episode_name is None:
                continue

            m = re.search(r'"(.*?)"', old_subj)
            if not m:
                continue

            fname = m.group(1)
            if episode_name:
                fname = fname.replace(old_subj.split('"')[1], episode_name)
            # Remove prefixo de pasta existente (pode ser nome ofuscado ou errado)
            if "/" in fname:
                fname = fname.split("/", 1)[1]

            if not fname:
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


def collect_season_nzbs(nzb_dir: str, season_prefix: str) -> list[tuple[str, str]]:
    """Encontra NZBs de episódios na pasta e retorna (path, episode_name).

    Extrai padrão de temporada (ex: S02E) do nome da pasta e procura por NZBs
    que contenham esse padrão. Extrai o nome do episódio a partir do subject
    do primeiro arquivo de dados encontrado em cada NZB.

    Retorna lista ordenada de (nzb_path, episode_name) para mesclar e corrigir subjects.
    """
    import glob
    import re
    from pathlib import Path

    ns_url = "http://www.newzbin.com/DTD/2003/nzb"
    nzb_dir_path = Path(nzb_dir)

    if not nzb_dir_path.exists():
        return []

    # Extrai padrão de temporada do folder name (ex: S02E de Rick.And.Morty.S02....)
    season_match = re.search(r'(S\d{2}E?)', season_prefix, re.IGNORECASE)
    if not season_match:
        return []

    season_pattern = season_match.group(1)

    # Procura por todos os NZBs e filtra os que contenham o padrão de temporada
    all_nzbs = sorted(glob.glob(str(nzb_dir_path / "*.nzb")))
    nzb_files = [f for f in all_nzbs if season_pattern in Path(f).stem]

    # Exclui o NZB final da temporada (que tem o mesmo nome da pasta)
    season_final_nzb = str(nzb_dir_path / f"{season_prefix}.nzb")
    nzb_files = [f for f in nzb_files if f != season_final_nzb]

    episode_data = []
    for nzb_path in nzb_files:
        ep_name = None
        try:
            tree = ET.parse(nzb_path)
            root = tree.getroot()

            # Encontra o primeiro arquivo de dados (não-.par2)
            files = root.findall(f".//{{{ns_url}}}file") or root.findall(".//file")
            for file_elem in files:
                subj = file_elem.get("subject", "")
                if subj and "par2" not in subj.lower():
                    # Tenta extrair o prefixo da pasta do subject
                    # Formato típico: "EP_NAME/filename" ou apenas "filename"
                    if "/" in subj:
                        ep_name = subj.split("/")[0]
                    else:
                        # Se não tem prefixo, usa o basename do NZB (sem .nzb)
                        ep_name = Path(nzb_path).stem
                    break
        except Exception as e:
            print(f"Aviso: não foi possível ler episódio de {Path(nzb_path).name}: {e}")
            continue

        if ep_name:
            episode_data.append((nzb_path, ep_name))

    return episode_data
