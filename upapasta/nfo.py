#!/usr/bin/env python3
"""
nfo.py

Geração de arquivos .nfo para uploads na Usenet.

- Arquivo único: usa mediainfo para gerar descrição técnica.
- Pasta: gera árvore de diretórios + estatísticas + metadados de vídeo (ffprobe).
"""

import os
import re
import subprocess


def find_mediainfo() -> str | None:
    """Procura executável 'mediainfo' no PATH."""
    import shutil
    for cmd in ("mediainfo", "mediainfo.exe"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def _get_video_duration(file_path: str) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _get_video_metadata(file_path: str) -> dict:
    metadata = {"codec": "N/A", "resolution": "N/A", "bitrate": "N/A"}
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", check=True)
        data = result.stdout.strip().split("\n")
        if len(data) >= 3:
            metadata["codec"] = data[0] if data[0] != "N/A" else "N/A"
            metadata["resolution"] = f"{int(data[1])}x{int(data[2])}"
        if len(data) >= 4 and data[3].isdigit() and int(data[3]) > 0:
            metadata["bitrate"] = f"{int(data[3]) / 1000:.0f} kbps"
    except Exception:
        pass
    return metadata


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _normalize_text(text: str) -> str:
    table = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
    )
    return text.translate(table)


def _generate_tree(start_path: str, video_metadata_map: dict) -> tuple[list[str], int, int]:
    if not os.path.isdir(start_path):
        return [], 0, 0

    lines = []
    file_count = 0
    dir_count = 0
    current_nfo_name = os.path.basename(start_path) + ".nfo"

    def _walk(current_dir: str, prefix: str = "") -> None:
        nonlocal file_count, dir_count
        contents = [c for c in sorted(os.listdir(current_dir), key=str.lower) if c != current_nfo_name]
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
                meta_line = ""
                key = os.path.abspath(path)
                if key in video_metadata_map:
                    m = video_metadata_map[key]
                    meta_line = f" | {m.get('duration_str', '00:00:00')} | {m.get('resolution', 'N/A'):<10} | {m.get('codec', 'N/A'):<10} | {m.get('bitrate', 'N/A'):<10}"
                lines.append(f"{prefix}{pointer}{normalized}{meta_line}")

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
        "|          automated usenet uploader  //  github.com/franzopl/upapasta        |\n"
        "|                                                                              |\n"
        "'------------------------------------------------------------------------------'"
    )


def generate_nfo_single_file(input_path: str, nfo_path: str) -> bool:
    """Gera .nfo com saída do mediainfo para um arquivo único."""
    mediainfo_path = find_mediainfo()
    if not mediainfo_path:
        print("Atenção: 'mediainfo' não encontrado. Pulando geração de .nfo.")
        return False

    try:
        proc = subprocess.run([mediainfo_path, input_path], capture_output=True, text=True, check=True)
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

        with open(nfo_path, "w", encoding="utf-8") as f:
            f.write(output)
        return True
    except Exception as e:
        print(f"Atenção: falha ao gerar NFO com mediainfo: {e}")
        return False


def generate_nfo_folder(input_path: str, nfo_path: str, banner: str | None = None) -> bool:
    """Gera .nfo detalhado para uma pasta com árvore e estatísticas."""
    from pathlib import Path

    try:
        folder_name = os.path.basename(input_path.rstrip(os.sep))
        title_temp = folder_name

        year = "N/A"
        year_match = re.search(r"\[(\d{4})\]", title_temp)
        if year_match:
            year = year_match.group(1)
            title_temp = (title_temp[: year_match.start()] + title_temp[year_match.end():]).strip()

        producer_match = re.search(r"\[([^\]]+)\]$", title_temp)
        if producer_match:
            producer = producer_match.group(1).strip()
            title_temp = title_temp[: producer_match.start()].strip()
        else:
            producer = "Desconhecido"

        title = title_temp
        if year != "N/A":
            title += f" [{year}]"
        title += f" [{producer}]"
        title = _normalize_text(title)
        producer = _normalize_text(producer)

        root_path = Path(input_path)
        all_files = [p for p in root_path.rglob("*") if p.is_file() and p.name != f"{folder_name}.nfo"]
        video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm", ".wmv"}
        video_files = [f for f in all_files if f.suffix.lower() in video_exts]

        video_metadata_map = {}
        total_duration_seconds = 0.0
        for video in video_files:
            duration_sec = _get_video_duration(str(video))
            meta = _get_video_metadata(str(video))
            meta["duration_str"] = _format_duration(duration_sec)
            total_duration_seconds += duration_sec
            video_metadata_map[os.path.abspath(video)] = meta

        tree_lines, total_dirs, total_files_in_tree = _generate_tree(input_path, video_metadata_map)

        extension_counts: dict[str, int] = {}
        for f in all_files:
            ext = f.suffix.lower() if f.suffix else ".sem_extensao"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

        def center(text: str, width: int = 78) -> str:
            return text.center(width)

        lines: list[str] = []

        if banner:
            lines.extend(banner.replace("\\n", "\n").split("\n"))
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
            f"  > Diretorios: {total_dirs}",
            f"  > Total de Arquivos: {len(all_files)}",
        ]

        if total_duration_seconds > 0:
            lines.append(f"  > Duracao Total de Video: {_format_duration(total_duration_seconds)} ({total_duration_seconds / 3600:.2f} horas)")

        lines.append("  > Arquivos por Tipo:")
        for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    - {ext.upper().replace('.', '')}: {count} arquivo(s)")

        lines += [
            "",
            "",
            "+" + "-" * 78 + "+",
            "|" + center("*** ESTRUTURA DE ARQUIVOS E DIRETORIOS ***") + "|",
            "+" + "-" * 78 + "+",
            "",
        ]
        lines.extend(tree_lines)
        lines.append(f"\n{total_dirs} diretorios, {total_files_in_tree} arquivos")

        with open(nfo_path, "w", encoding="cp1252", errors="replace") as f:
            f.write("\n".join(lines))
        return True
    except Exception as e:
        print(f"Atenção: falha ao gerar NFO de pasta: {e}")
        return False
