#!/usr/bin/env python3
"""
nzb.py

Utilitários compartilhados para resolução de caminho, tratamento de conflitos
e correção de subjects em arquivos NZB.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Any

from .config import render_template
from .i18n import _


def resolve_nzb_template(env_vars: dict[str, str], is_folder: bool, skip_rar: bool) -> str:
    """Retorna o template NZB_OUT a ser usado."""
    template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT")
    if not template:
        return "{filename}.nzb"

    # Se o template aponta para um diretório existente, termina com barra
    # ou não contém o template/extensão esperada, anexar automaticamente {filename}.nzb
    if "{filename}" not in template:
        if (
            os.path.isdir(template)
            or template.endswith("/")
            or template.endswith("\\")
            or not template.lower().endswith(".nzb")
        ):
            return os.path.join(template, "{filename}.nzb")

    return template


def resolve_nzb_basename(
    input_path: str,
    is_folder: bool,
    obfuscated_map: dict[str, str] | None = None,
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
    env_vars: dict[str, str],
    is_folder: bool,
    skip_rar: bool,
    working_dir: str,
    obfuscated_map: dict[str, str] | None = None,
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
    env_vars: dict[str, str],
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
        print(
            _(
                "Aviso: arquivo NZB já existe: {path} - sobrescrevendo por solicitação (overwrite)"
            ).format(path=nzb_out_abs)
        )
    elif nzb_conflict == "fail":
        print(
            _("Erro: arquivo NZB já existe: {path}. Parando por configuração 'fail'.").format(
                path=nzb_out_abs
            )
        )
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
        print(
            _("Aviso: arquivo NZB já existe - usando novo nome: {name}").format(
                name=os.path.basename(candidate)
            )
        )

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

        meta_elem = root.find(f".//{{{ns}}}meta[@type='password']")
        if meta_elem is None:
            meta_elem = root.find(".//meta[@type='password']")

        if meta_elem is not None:
            meta_elem.text = password
        else:
            meta_elem = ET.SubElement(head, f"{{{ns}}}meta")
            meta_elem.set("type", "password")
            meta_elem.text = password

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
    except Exception as e:
        print(_("Aviso: não foi possível injetar senha no NZB: {error}").format(error=e))


def enrich_nzb_metadata(nzb_path: str, metadata: dict[str, Any]) -> None:
    """Enriquece o NZB com metadados do TMDb (título, poster, IMDB, etc.)."""
    try:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        head = root.find(f"{{{ns}}}head") or root.find("head")
        if head is None:
            head = ET.Element(f"{{{ns}}}head")
            root.insert(0, head)

        # Mapeamento de chaves TMDb para tipos de meta NZB (Newznab standard)
        mapping = {
            "title": "title",
            "name": "title",
            "poster_path": "poster",
            "imdb_id": "imdb",
            "genres": "tag",
            "tagline": "tagline",
        }

        # Remove metas antigos do mesmo tipo para evitar duplicidade
        types_to_add = set(mapping.values())
        for meta in list(head):
            if meta.get("type") in types_to_add:
                head.remove(meta)

        for key, meta_type in mapping.items():
            val = metadata.get(key)
            if not val:
                continue

            # Formatação especial para poster
            if key == "poster_path":
                val = f"https://image.tmdb.org/t/p/original{val}"

            # Se for lista (gêneros), adiciona múltiplos elementos do mesmo tipo
            if isinstance(val, list):
                for item in val:
                    m = ET.SubElement(head, f"{{{ns}}}meta")
                    m.set("type", meta_type)
                    m.text = str(item)
            else:
                m = ET.SubElement(head, f"{{{ns}}}meta")
                m.set("type", meta_type)
                m.text = str(val)

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
    except Exception as e:
        print(_("Aviso: não foi possível enriquecer metadados no NZB: {error}").format(error=e))


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
    m_yenc = re.search(r"^(.*?)(\s+yEnc\s+\(\d+/\d+\).*)$", subject)
    if m_yenc:
        pre = m_yenc.group(1)
        suffix = m_yenc.group(2)
        # O último token de `pre` é o nome do arquivo
        idx = pre.rfind(" ")
        if idx >= 0:
            return pre[: idx + 1], pre[idx + 1 :], suffix
        return "", pre, suffix

    m_part = re.search(r"^(.*?)(\s*\(\d+/\d+\).*)$", subject)
    if m_part:
        pre = m_part.group(1)
        suffix = m_part.group(2)
        idx = pre.rfind(" ")
        if idx >= 0:
            return pre[: idx + 1], pre[idx + 1 :], suffix
        return "", pre, suffix

    # Caso 3: subject é apenas o nome do arquivo (sem indicadores)
    return "", subject, ""


def _deobfuscate_filename(
    current_filename: str,
    obfuscated_map: dict[str, str],
) -> str:
    """Resolve o nome original a partir do mapa de ofuscação.

    Trata extensões compostas (.part01.rar, .vol00+01.par2, .par2) e simples.
    Devolve current_filename se não encontrar mapeamento.
    """
    if current_filename in obfuscated_map:
        return obfuscated_map[current_filename]

    # Extensões compostas: .partNN.rar e .volNN+MM.par2 / .par2
    for pattern in (
        r"(\.part\d+\.rar)$",
        r"(\.vol\d+\+\d+\.par2)$",
        r"(\.par2)$",
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
    obfuscated_map: dict[str, str] | None = None,
    file_sizes: dict[str, int] | None = None,
    article_size_bytes: int = 716800,
) -> None:
    """Adiciona prefixo de pasta ao subject do NZB quando necessário.

    Quando file_sizes é fornecido, faz matching por contagem de segmentos para
    associar corretamente o nome da pasta a cada arquivo — necessário porque
    o nyuu não preserva a ordem de upload no NZB.

    Com --obfuscate, mantém nomes aleatórios no NZB. O PAR2 contém os nomes
    reais internamente e os restaura automaticamente na verificação.
    """
    try:
        ns_url = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns_url)
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        files = root.findall(f".//{{{ns_url}}}file")
        if not files:
            files = root.findall(".//file")

        # Quando file_sizes está disponível, constrói mapeamento segs→filename.
        # O nyuu não preserva a ordem de upload no NZB, então não se pode usar
        # o índice da file_list — match por tamanho é o único método confiável.
        # Quando file_sizes está disponível, monta seg_count -> [lista_de_arquivos] para matching.
        # Usamos uma lista porque múltiplos arquivos podem ter o mesmo tamanho (mesma contagem de segmentos).
        seg_to_files: dict[int, list[str]] = {}
        if file_list and file_sizes:
            for fname in file_list:
                size = file_sizes.get(fname)
                if size is not None:
                    expected_segs = max(1, math.ceil(size / article_size_bytes))
                    seg_to_files.setdefault(expected_segs, []).append(fname)

        # from_file_list: fallback index-based quando não há tamanhos disponíveis.
        from_file_list = bool(not seg_to_files and file_list and len(file_list) == len(files))

        for i, file_elem in enumerate(files):
            old_subject = file_elem.get("subject", "")

            if seg_to_files:
                # Match por contagem de segmentos (confiável, ordem-independente)
                nzb_segs = len(
                    file_elem.findall(f".//{{{ns_url}}}segment") or file_elem.findall(".//segment")
                )

                # Pega o próximo arquivo disponível com essa contagem de segmentos
                file_options = seg_to_files.get(nzb_segs)
                if file_options:
                    current_filename = file_options.pop(0)
                else:
                    # Vizinho mais próximo se a contagem exata não existir (raro)
                    closest_seg = min(seg_to_files.keys(), key=lambda k: abs(k - nzb_segs))
                    current_filename = seg_to_files[closest_seg].pop(0)
                    if not seg_to_files[closest_seg]:
                        del seg_to_files[closest_seg]
                prefix, suffix = "", ""
            elif from_file_list:
                # Index-based: usado quando file_sizes não está disponível (ex: testes, --season)
                current_filename = file_list[i]  # type: ignore[index]
                prefix, suffix = "", ""
            else:
                prefix, current_filename, suffix = _parse_subject(old_subject)

            if not current_filename:
                continue

            # Com --obfuscate, mantém o nome aleatório no NZB.
            # O PAR2 contém os nomes reais internamente.
            if folder_name:
                final_filename = f"{folder_name}/{current_filename}"
            else:
                final_filename = current_filename

            # Reconstrói o subject preservando prefixo e sufixo
            quoted = '"' in old_subject
            if quoted:
                new_subject = f'{prefix}"{final_filename}"{suffix}'
            else:
                new_subject = f"{prefix}{final_filename}{suffix}"

            file_elem.set("subject", new_subject)

        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
        print(_("NZB corrigido: subjects dos arquivos de dados atualizados."))
    except Exception as e:
        print(_("Aviso: não foi possível corrigir o NZB: {error}").format(error=e))


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
        from .i18n import _

        print(_("Erro ao mesclar NZBs: {error}").format(error=e))
        return False
