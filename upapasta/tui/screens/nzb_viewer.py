"""
tui/screens/nzb_viewer.py

Tela de visualização inline de NZB após upload concluído.
Exibe metadados do cabeçalho e lista de arquivos/segmentos.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Rule, Static

_NS = "http://www.newzbin.com/DTD/2003/nzb"

# Fallback de tamanho de artigo quando o atributo bytes do segmento está ausente.
_FALLBACK_ARTICLE_SIZE = 750_000  # 750 KB


def _parse_nzb(path: str) -> tuple[dict[str, list[str]], list[dict[str, object]]]:
    """
    Parseia um NZB e retorna (meta, files).

    meta: dict com listas de valores por tipo (title, password, tag, poster…)
    files: list de dicts com keys: subject, poster, date, groups, segments (int), size_est (bytes)

    O tamanho (size_est) é a soma dos atributos `bytes` reais de cada <segment>;
    segmentos sem o atributo caem no fallback de tamanho de artigo padrão.
    """
    meta: dict[str, list[str]] = {}
    files: list[dict[str, object]] = []

    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return meta, files

    root = tree.getroot()

    # Suporte a namespace ou sem namespace
    def _tag(local: str) -> str:
        return f"{{{_NS}}}{local}"

    for m in root.findall(f".//{_tag('meta')}"):
        t = m.get("type", "")
        v = (m.text or "").strip()
        if t and v:
            meta.setdefault(t, []).append(v)

    for f in root.findall(f".//{_tag('file')}"):
        subject = f.get("subject", "")
        poster = f.get("poster", "")
        date = f.get("date", "")
        segs = f.findall(f".//{_tag('segment')}")
        seg_count = len(segs)
        # Soma os bytes reais declarados em cada segmento; fallback se ausente.
        size_est = 0
        for seg in segs:
            raw_bytes = seg.get("bytes")
            try:
                size_est += int(raw_bytes) if raw_bytes else _FALLBACK_ARTICLE_SIZE
            except ValueError:
                size_est += _FALLBACK_ARTICLE_SIZE

        grps: list[str] = []
        for g in f.findall(f".//{_tag('group')}"):
            if g.text:
                grps.append(g.text.strip())

        files.append(
            {
                "subject": subject,
                "poster": poster,
                "date": date,
                "groups": grps,
                "segments": seg_count,
                "size_est": size_est,
            }
        )

    return meta, files


def _fmt_size(n: int) -> str:
    if n >= 1_073_741_824:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    return f"{n / 1024:.0f} KB"


def _extract_filename(subject: str) -> str:
    """Extrai nome de arquivo do campo subject do NZB."""
    # Tenta formato com aspas: "filename.ext"
    import re

    m = re.search(r'"([^"]+)"', subject)
    if m:
        return m.group(1)
    # Tenta formato yEnc: ... filename.ext yEnc (N/M)
    m = re.search(r"(\S+)\s+yEnc\s+\(", subject)
    if m:
        return m.group(1)
    # Fallback: retorna o subject truncado
    return subject[:60] + ("…" if len(subject) > 60 else "")


class NzbViewerScreen(Screen[None]):
    """Tela de visualização inline do NZB gerado."""

    BINDINGS = [
        Binding("escape,q", "dismiss", "Fechar"),
        Binding("j,down", "scroll_down", "↓", show=False),
        Binding("k,up", "scroll_up", "↑", show=False),
    ]

    DEFAULT_CSS = """
    NzbViewerScreen {
        background: $surface;
    }

    #nzb-header-box {
        padding: 1 2;
        background: $panel;
        border: tall $accent;
        margin: 1 1 0 1;
        height: auto;
    }

    .nzb-meta-label {
        color: $text-muted;
    }

    .nzb-meta-value {
        color: $text;
        text-style: bold;
    }

    #nzb-files-label {
        margin: 1 1 0 1;
        color: $accent;
        text-style: bold;
    }

    #nzb-table {
        margin: 0 1 1 1;
        height: 1fr;
    }

    #nzb-not-found {
        padding: 2;
        color: $error;
        text-align: center;
    }
    """

    def __init__(self, nzb_path: str) -> None:
        super().__init__()
        self._nzb_path = nzb_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield from self._build_content()

    def _build_content(self) -> ComposeResult:
        if not os.path.isfile(self._nzb_path):
            yield Static(
                f"Arquivo NZB não encontrado:\n{self._nzb_path}",
                id="nzb-not-found",
            )
            return

        meta, files = _parse_nzb(self._nzb_path)

        total_segs = sum(int(f["segments"]) for f in files)  # type: ignore[arg-type]
        total_size = sum(int(f["size_est"]) for f in files)  # type: ignore[arg-type]
        basename = os.path.basename(self._nzb_path)

        # Cabeçalho com metadados
        with Vertical(id="nzb-header-box"):
            yield Static(
                Text.assemble(
                    ("Arquivo: ", "dim"),
                    (basename, "bold cyan"),
                ),
            )
            yield Static(
                Text.assemble(
                    ("Arquivos: ", "dim"),
                    (str(len(files)), "bold"),
                    ("  •  Segmentos: ", "dim"),
                    (str(total_segs), "bold"),
                    ("  •  Tamanho estimado: ", "dim"),
                    (_fmt_size(total_size), "bold green"),
                ),
            )

            # Metadados do cabeçalho (title, password, tags…)
            if meta:
                yield Rule()
                for key, values in meta.items():
                    label_map = {
                        "title": "Título",
                        "password": "Senha",
                        "tag": "Tags",
                        "poster": "Poster",
                    }
                    label = label_map.get(key, key.capitalize())
                    val_str = ", ".join(values)
                    yield Static(
                        Text.assemble(
                            (f"{label}: ", "dim"),
                            (val_str, "bold"),
                        )
                    )

        # Tabela de arquivos
        yield Label(f"  Conteúdo ({len(files)} arquivo(s))", id="nzb-files-label")

        table: DataTable[str] = DataTable(id="nzb-table", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        basename = os.path.basename(self._nzb_path)
        self.title = f"UpaPasta — NZB: {basename}"
        self.sub_title = self._nzb_path

        if not os.path.isfile(self._nzb_path):
            return

        _meta, files = _parse_nzb(self._nzb_path)

        table = self.query_one("#nzb-table", DataTable)
        table.add_columns("#", "Arquivo", "Segmentos", "Tamanho Est.", "Grupo(s)")

        for i, f in enumerate(files, 1):
            fname = _extract_filename(str(f["subject"]))
            segs = str(f["segments"])
            size = _fmt_size(int(f["size_est"]))  # type: ignore[arg-type]
            groups = ", ".join(f["groups"]) if f["groups"] else "—"  # type: ignore[index]
            table.add_row(str(i), fname, segs, size, groups)

        if files:
            table.focus()

    def action_scroll_down(self) -> None:
        table = self.query_one("#nzb-table", DataTable)
        table.action_scroll_down()

    def action_scroll_up(self) -> None:
        table = self.query_one("#nzb-table", DataTable)
        table.action_scroll_up()
