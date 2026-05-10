#!/usr/bin/env python3
"""
nfo.py

Geração de arquivos .nfo para uploads na Usenet.

- Arquivo único: usa mediainfo para gerar descrição técnica.
- Pasta: gera árvore de diretórios + estatísticas + metadados de vídeo (ffprobe).
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Optional

from .i18n import _
from .tools import get_tool_path


def find_mediainfo() -> str | None:
    for cmd in ("mediainfo", "mediainfo.exe"):
        path = get_tool_path(cmd)
        if path:
            return path
    return None


def find_ffprobe() -> str | None:
    for cmd in ("ffprobe", "ffprobe.exe"):
        path = get_tool_path(cmd)
        if path:
            return path
    return None


def center(text: str, width: int = 78) -> str:
    return text.center(width)


def _format_size(size_bytes: int) -> str:
    size_float: float = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_float < 1024 or unit == "TB":
            return f"{size_float:.2f} {unit}" if unit != "B" else f"{int(size_float)} {unit}"
        size_float /= 1024
    return f"{size_float:.2f} TB"


def _get_video_info(file_path: str) -> tuple[float, dict[str, Any]]:
    """Retorna (duration_seconds, metadata) com uma única chamada ao ffprobe.

    metadata inclui: codec, resolution, bitrate, audio_tracks, subtitle_tracks.
    audio_tracks e subtitle_tracks são listas de códigos de idioma (ex: ['PT', 'EN']).
    """
    import json as _json

    duration = 0.0
    metadata: dict[str, Any] = {
        "codec": "N/A",
        "resolution": "N/A",
        "bitrate": "N/A",
        "audio_tracks": [],
        "subtitle_tracks": [],
    }
    try:
        ffprobe_exe = find_ffprobe()
        if not ffprobe_exe:
            return 0.0, metadata

        cmd = [
            ffprobe_exe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,tags:format=duration,bit_rate",
            "-of",
            "json",
            file_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", check=True
        )
        data = _json.loads(result.stdout)
        fmt = data.get("format", {})
        try:
            duration = float(fmt.get("duration") or 0)
        except (ValueError, TypeError):
            duration = 0.0
        try:
            br = int(fmt.get("bit_rate") or 0)
            if br > 0:
                metadata["bitrate"] = f"{br / 1000:.0f} kbps"
        except (ValueError, TypeError):
            pass

        audio_langs: list[str] = []
        sub_langs: list[str] = []
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type", "")
            codec_name = stream.get("codec_name", "") or ""
            tags = stream.get("tags") or {}
            lang = (tags.get("language") or tags.get("LANGUAGE") or "").strip().upper()
            # "und" = idioma indefinido — mostra codec como fallback
            if lang in ("", "UND"):
                lang = codec_name.upper() or "?"

            if codec_type == "video":
                metadata["codec"] = codec_name or "N/A"
                w, h = stream.get("width"), stream.get("height")
                if w and h:
                    metadata["resolution"] = f"{w}x{h}"
            elif codec_type == "audio":
                audio_langs.append(lang)
            elif codec_type == "subtitle":
                sub_langs.append(lang)

        metadata["audio_tracks"] = audio_langs
        metadata["subtitle_tracks"] = sub_langs
    except Exception:
        pass
    return duration, metadata


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _normalize_text(text: str) -> str:
    table = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
    )
    return text.translate(table)


_MAX_FILENAME_LEN = 42


def _generate_tree(
    start_path: str, video_metadata_map: dict[str, Any], file_sizes: dict[str, int]
) -> tuple[list[str], int, int]:
    if not os.path.isdir(start_path):
        return [], 0, 0

    lines = []
    file_count = 0
    dir_count = 0
    current_nfo_name = os.path.basename(start_path) + ".nfo"

    def _walk(current_dir: str, prefix: str = "") -> None:
        nonlocal file_count, dir_count
        contents = [
            c for c in sorted(os.listdir(current_dir), key=str.lower) if c != current_nfo_name
        ]
        for i, item in enumerate(contents):
            path = os.path.join(current_dir, item)
            pointer = "`-- " if i == len(contents) - 1 else "|-- "
            new_prefix = prefix + ("    " if i == len(contents) - 1 else "|   ")
            normalized = _normalize_text(item)
            if os.path.isdir(path):
                lines.append(f"{prefix}{pointer}{normalized}")
                dir_count += 1
                _walk(path, new_prefix)
            else:
                file_count += 1
                display_name = (
                    (normalized[:_MAX_FILENAME_LEN] + "...")
                    if len(normalized) > _MAX_FILENAME_LEN
                    else normalized
                )
                key = os.path.abspath(path)
                size_str = _format_size(file_sizes.get(key, 0))
                meta_line = f" [{size_str}]"
                if key in video_metadata_map:
                    m = video_metadata_map[key]
                    meta_line += f" | {m.get('duration_str', '00:00:00')} | {m.get('resolution', 'N/A'):<10} | {m.get('codec', 'N/A'):<6} | {m.get('bitrate', 'N/A')}"
                    audio = m.get("audio_tracks", [])
                    subs = m.get("subtitle_tracks", [])
                    if audio:
                        meta_line += f" | Áud: {', '.join(audio)}"
                    if subs:
                        meta_line += f" | Sub: {', '.join(subs)}"
                lines.append(f"{prefix}{pointer}{display_name}{meta_line}")

    lines.append(_normalize_text(os.path.basename(start_path)))
    _walk(start_path)
    return lines, dir_count, file_count


def _default_banner() -> str:
    return (
        ".------------------------------------------------------------------------------.\n"
        "|                                                                              |\n"
        "|    _   _ ____  _    ____   _    ____ _____  _                               |\n"
        "|   | | | |  _ \\/ \\  |  _ \\ / \\  / ___|_   _|/ \\                            |\n"
        "|   | | | | |_) / _ \\ | |_) / _ \\ \\___ \\ | | / _ \\                          |\n"
        "|   | |_| |  __/ ___ \\|  __/ ___ \\ ___) || |/ ___ \\                         |\n"
        "|    \\___/|_| /_/   \\_\\_| /_/   \\_\\____/ |_/_/   \\_\\                        |\n"
        "|                                                                              |\n"
        "|                    automated usenet uploader                                  |\n"
        "|                                                                              |\n"
        "'------------------------------------------------------------------------------'"
    )


def _format_tmdb_section(data: dict[str, Any]) -> list[str]:
    """Formata os metadados do TMDb em uma seção visual."""
    title = data.get("title") or data.get("name", "N/A")
    year = (data.get("release_date") or data.get("first_air_date") or "N/A")[:4]
    genres = ", ".join(data.get("genres", []))
    overview = data.get("overview", "N/A")
    imdb_id = data.get("imdb_id")
    poster_path = data.get("poster_path")

    lines = [
        "",
        "+" + "-" * 78 + "+",
        "|" + center("*** METADADOS TMDB ***") + "|",
        "+" + "-" * 78 + "+",
        "",
        f"  > Titulo:     {title}",
        f"  > Ano:        {year}",
    ]
    if genres:
        lines.append(f"  > Generos:    {genres}")
    if imdb_id:
        lines.append(f"  > IMDB:       https://www.imdb.com/title/{imdb_id}")
    if poster_path:
        lines.append(f"  > Poster:     https://image.tmdb.org/t/p/original{poster_path}")

    # Encurta a sinopse se for muito longa
    lines.append("  > Sinopse:")
    import textwrap

    for line in textwrap.wrap(overview, width=74):
        lines.append(f"    {line}")

    return lines


def generate_nfo_from_template(
    template_path: str,
    input_path: str,
    nfo_path: str,
    tmdb_metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """Gera .nfo a partir de um arquivo de template, substituindo placeholders."""
    if not os.path.exists(template_path):
        print(_("Atenção: arquivo de template não encontrado: {path}").format(path=template_path))
        return False

    try:
        from pathlib import Path

        # 1. Coleta metadados básicos
        folder_name = os.path.basename(input_path.rstrip(os.sep))
        clean_title, clean_year = folder_name, "N/A"
        # Tenta extrair ano básico do nome
        year_match = re.search(r"[\s._\[(](19\d{2}|20[0-2]\d)([\s._\])]|$)", folder_name)
        if year_match:
            clean_year = year_match.group(1)
            clean_title = (
                folder_name[: year_match.start()] + folder_name[year_match.end() :]
            ).strip()
            # Remove extensões se sobrar
            clean_title = re.sub(
                r"\.(mkv|mp4|avi|mov|rar|7z)$", "", clean_title, flags=re.IGNORECASE
            )
            clean_title = clean_title.replace(".", " ").strip()

        # 2. Coleta dados do TMDb
        tmdb = tmdb_metadata or {}
        title = tmdb.get("title") or tmdb.get("name") or clean_title
        year = (tmdb.get("release_date") or tmdb.get("first_air_date") or clean_year)[:4]
        synopsis = tmdb.get("overview") or "N/A"
        genres = ", ".join(tmdb.get("genres", [])) or "N/A"
        imdb_id = tmdb.get("imdb_id")
        imdb_url = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "N/A"
        poster_path = tmdb.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else "N/A"

        # 3. Coleta dados de arquivos
        is_dir = os.path.isdir(input_path)
        if is_dir:
            root_path = Path(input_path)
            all_files = [
                p for p in root_path.rglob("*") if p.is_file() and p.name != f"{folder_name}.nfo"
            ]
            file_sizes: dict[str, int] = {os.path.abspath(f): f.stat().st_size for f in all_files}
            total_size_bytes = sum(file_sizes.values())

            # Gera árvore
            video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm", ".wmv"}
            video_files = [f for f in all_files if f.suffix.lower() in video_exts]
            video_metadata_map = {}
            for video in video_files:
                duration_sec, meta = _get_video_info(str(video))
                meta["duration_str"] = _format_duration(duration_sec)
                video_metadata_map[os.path.abspath(video)] = meta

            tree_lines, total_dirs, total_files = _generate_tree(
                input_path, video_metadata_map, file_sizes
            )
            files_content = "\n".join(tree_lines)

            # Mediainfo do primeiro video representativo
            mi_target = _find_first_episode(input_path)
        else:
            total_size_bytes = os.path.getsize(input_path)
            files_content = os.path.basename(input_path)
            mi_target = input_path

        size_str = _format_size(total_size_bytes)

        # 4. Mediainfo
        mediainfo_content = "N/A"
        if mi_target:
            mi_exe = find_mediainfo()
            if mi_exe:
                try:
                    res = subprocess.run(
                        [mi_exe, mi_target], capture_output=True, text=True, check=True
                    )
                    mediainfo_content = res.stdout
                except Exception:
                    pass

        # 5. Substituição
        with open(template_path, "r", encoding="utf-8", errors="ignore") as tf:
            content = tf.read()

        replacements = {
            "{{title}}": title,
            "{{year}}": year,
            "{{synopsis}}": synopsis,
            "{{overview}}": synopsis,
            "{{genres}}": genres,
            "{{imdb_url}}": imdb_url,
            "{{poster_url}}": poster_url,
            "{{size}}": size_str,
            "{{files}}": files_content,
            "{{mediainfo}}": mediainfo_content,
        }

        for placeholder, value in replacements.items():
            content = content.replace(placeholder, str(value))

        with open(nfo_path, "w", encoding="utf-8") as nf:
            nf.write(content)

        return True
    except Exception as e:
        print(_("Erro ao gerar NFO a partir do template: {error}").format(error=e))
        return False


def generate_nfo_single_file(
    input_path: str, nfo_path: str, tmdb_metadata: Optional[dict[str, Any]] = None
) -> bool:
    """Gera .nfo com saída do mediainfo para um arquivo único."""
    mediainfo_path = find_mediainfo()
    if not mediainfo_path:
        print(_("Atenção: 'mediainfo' não encontrado. Pulando geração de .nfo."))
        return False

    try:
        proc = subprocess.run(
            [mediainfo_path, input_path], capture_output=True, text=True, check=True
        )
        output = proc.stdout

        video_exts = (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm")
        if os.path.splitext(input_path)[1].lower() in video_exts:
            filename_only = os.path.basename(input_path)
            lines = []
            for line in output.splitlines():
                if re.match(r"^\s*Complete name\s*:\s*", line, flags=re.IGNORECASE):
                    parts = line.split(":", 1)
                    lines.append(f"{parts[0]}: {filename_only}")
                else:
                    lines.append(line)
            output = "\n".join(lines) + ("\n" if proc.stdout.endswith("\n") else "")

        if tmdb_metadata:
            tmdb_lines = _format_tmdb_section(tmdb_metadata)
            output += "\n" + "\n".join(tmdb_lines) + "\n"

        with open(nfo_path, "w", encoding="utf-8") as f:
            f.write(output)
        return True
    except Exception as e:
        print(_("Atenção: falha ao gerar NFO com mediainfo: {error}").format(error=e))
        return False


def _is_series_folder(folder_name: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])S\d{2}(?:E\d{2})?(?![0-9])", folder_name, re.IGNORECASE))


def _find_first_episode(folder_path: str) -> str | None:
    video_exts = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".ts", ".webm"}
    candidates = []
    for root, _d, files in os.walk(folder_path):
        for f in files:
            if os.path.splitext(f)[1].lower() in video_exts:
                candidates.append(os.path.join(root, f))
    if not candidates:
        return None
    return sorted(candidates)[0]


def generate_nfo_folder(
    input_path: str,
    nfo_path: str,
    banner: str | None = None,
    tmdb_metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """Gera .nfo detalhado para uma pasta.

    Para pastas de série (padrão SXX no nome): usa mediainfo do primeiro episódio.
    Para pastas genéricas: gera árvore de arquivos + estatísticas.
    """
    from pathlib import Path

    try:
        folder_name = os.path.basename(input_path.rstrip(os.sep))

        if _is_series_folder(folder_name):
            first_ep = _find_first_episode(input_path)
            if first_ep:
                return generate_nfo_single_file(first_ep, nfo_path, tmdb_metadata=tmdb_metadata)

        title_temp = folder_name

        year = "N/A"
        # suporta [2024] e (2024)
        year_match = re.search(r"[\[(](\d{4})[\])]", title_temp)
        if year_match:
            year = year_match.group(1)
            title_temp = (title_temp[: year_match.start()] + title_temp[year_match.end() :]).strip()

        title = title_temp
        if year != "N/A":
            title += f" [{year}]"
        title = _normalize_text(title)

        root_path = Path(input_path)
        all_files = [
            p for p in root_path.rglob("*") if p.is_file() and p.name != f"{folder_name}.nfo"
        ]
        video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm", ".wmv"}
        video_files = [f for f in all_files if f.suffix.lower() in video_exts]

        file_sizes: dict[str, int] = {os.path.abspath(f): f.stat().st_size for f in all_files}
        total_size = sum(file_sizes.values())

        video_metadata_map = {}
        total_duration_seconds = 0.0
        for video in video_files:
            duration_sec, meta = _get_video_info(str(video))
            meta["duration_str"] = _format_duration(duration_sec)
            total_duration_seconds += duration_sec
            video_metadata_map[os.path.abspath(video)] = meta

        tree_lines, total_dirs, total_files_in_tree = _generate_tree(
            input_path, video_metadata_map, file_sizes
        )

        extension_counts: dict[str, int] = {}
        for f in all_files:
            ext = f.suffix.lower() if f.suffix else ".sem_extensao"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

        lines: list[str] = []

        if banner:
            lines.extend(banner.split("\n"))
        else:
            lines.extend(_default_banner().split("\n"))
        lines.append("")

        lines += [
            "+" + "-" * 78 + "+",
            "|" + center(title.upper()) + "|",
            "+" + "-" * 78 + "+",
            "",
            "-" * 80,
            "",
            "+" + "-" * 78 + "+",
            "|" + center("*** ESTATISTICAS GERAIS ***") + "|",
            "+" + "-" * 78 + "+",
            "",
            f"  > Tamanho Total:      {_format_size(total_size)}",
            f"  > Diretorios:         {total_dirs}",
            f"  > Total de Arquivos:  {len(all_files)}",
        ]

        if total_duration_seconds > 0:
            lines.append(
                f"  > Duracao Total:      {_format_duration(total_duration_seconds)} ({total_duration_seconds / 3600:.2f} horas)"
            )

        # Exibe faixas de áudio e legendas do primeiro vídeo encontrado (representativo da release)
        if video_files and video_metadata_map:
            first_key = os.path.abspath(video_files[0])
            vm = video_metadata_map.get(first_key, {})
            audio_tracks: list[str] = vm.get("audio_tracks", [])
            sub_tracks: list[str] = vm.get("subtitle_tracks", [])
            if audio_tracks or sub_tracks:
                parts = []
                if audio_tracks:
                    parts.append(f"Audio: {', '.join(audio_tracks)}")
                if sub_tracks:
                    parts.append(f"Legendas: {', '.join(sub_tracks)}")
                lines.append(f"  > Faixas:             {' | '.join(parts)}")

        lines.append("  > Arquivos por Tipo:")
        for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    - {ext.upper().replace('.', '')}: {count} arquivo(s)")

        if tmdb_metadata:
            lines.extend(_format_tmdb_section(tmdb_metadata))

        lines += [
            "",
            "",
            "+" + "-" * 78 + "+",
            "|" + center("*** ESTRUTURA DE ARQUIVOS E DIRETORIOS ***") + "|",
            "+" + "-" * 78 + "+",
            "",
        ]
        lines.extend(tree_lines)
        lines.append(
            f"\n{total_dirs} diretorios, {total_files_in_tree} arquivos, {_format_size(total_size)}"
        )

        with open(nfo_path, "w", encoding="utf-8") as nfo_fh:
            nfo_fh.write("\n".join(lines))
        return True
    except Exception as e:
        print(_("Atenção: falha ao gerar NFO de pasta: {error}").format(error=e))
        return False
