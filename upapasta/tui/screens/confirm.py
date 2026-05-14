"""
tui/screens/confirm.py

Modal de confirmação pré-upload: exibe itens selecionados e permite escolher
opções básicas (--obfuscate, --rar, --par-profile) antes de iniciar.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Select, Static

from ..fs_scanner import FileNode, _fmt_size


@dataclass
class UploadConfig:
    obfuscate: bool
    use_rar: bool
    par_profile: str


def build_upload_cmd(item: FileNode, config: UploadConfig) -> list[str]:
    """Constrói o comando CLI para um item com as opções dadas."""
    cmd = [sys.executable, "-m", "upapasta", str(item.path), "--porcelain"]
    if config.obfuscate:
        cmd.append("--obfuscate")
    if config.use_rar:
        cmd.append("--rar")
    cmd.extend(["--par-profile", config.par_profile])
    return cmd


class ConfirmScreen(ModalScreen[Optional[UploadConfig]]):
    """Modal de confirmação de upload. Retorna UploadConfig ou None se cancelado."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #dialog {
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 35;
    }

    .title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .section-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    #items-list {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }

    #total-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    #par-estimate-label {
        color: $accent;
        margin-bottom: 1;
    }

    #options {
        height: auto;
        margin-bottom: 1;
    }

    #par-row {
        height: 3;
        align: left middle;
        margin-top: 0;
    }

    #par-label {
        width: auto;
        padding: 0 1 0 0;
    }

    #par-profile {
        width: 20;
    }

    #buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, items: list[FileNode]) -> None:
        super().__init__()
        self._items = items

    def compose(self) -> ComposeResult:
        total_bytes = sum(n.size for n in self._items if not n.is_dir)
        count = len(self._items)
        s = "ns" if count != 1 else ""

        with Vertical(id="dialog"):
            yield Label("Confirmar Upload", classes="title")

            yield Static(f"Item{s} selecionado{s} ({count}):", classes="section-label")
            with Vertical(id="items-list"):
                for item in self._items[:10]:
                    icon = "📁" if item.is_dir else "📄"
                    line = f"  {icon} {item.name}"
                    if not item.is_dir and item.size > 0:
                        line += f"  ({item.size_human})"
                    yield Static(line)
                if count > 10:
                    yield Static(f"  … e mais {count - 10} itens")

            if total_bytes > 0:
                yield Static(f"Total de arquivos: {_fmt_size(total_bytes)}", id="total-label")
            yield Static("", id="par-estimate-label")

            yield Static("Opções:", classes="section-label")
            with Vertical(id="options"):
                yield Checkbox("--obfuscate  (ofuscar nomes de arquivos)", id="obfuscate")
                yield Checkbox("--rar  (empacotar em RAR5 antes do upload)", id="use-rar")
                with Horizontal(id="par-row"):
                    yield Static("--par-profile:", id="par-label")
                    yield Select(
                        [("fast", "fast"), ("balanced", "balanced"), ("safe", "safe")],
                        value="balanced",
                        id="par-profile",
                    )

            with Horizontal(id="buttons"):
                yield Button("Cancelar", variant="default", id="btn-cancel")
                yield Button("Iniciar upload", variant="primary", id="btn-confirm")

    def on_mount(self) -> None:
        self._update_par_estimate()

    def on_select_changed(self) -> None:
        self._update_par_estimate()

    def _update_par_estimate(self) -> None:
        total_bytes = sum(n.size for n in self._items if not n.is_dir)
        if total_bytes == 0:
            return
        par_val = self.query_one("#par-profile", Select).value
        profile = str(par_val) if par_val is not Select.BLANK else "balanced"
        # Redundância aproximada por perfil
        redundancy = {"fast": 0.05, "balanced": 0.10, "safe": 0.20}.get(profile, 0.10)
        par_bytes = int(total_bytes * redundancy)
        total_with_par = total_bytes + par_bytes
        label = self.query_one("#par-estimate-label", Static)
        label.update(
            f"PAR2 ({profile}, ~{int(redundancy * 100)}%): +{_fmt_size(par_bytes)}"
            f"  →  total estimado: {_fmt_size(total_with_par)}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-confirm":
            self._dismiss_with_config()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _dismiss_with_config(self) -> None:
        par_val = self.query_one("#par-profile", Select).value
        par_profile = str(par_val) if par_val is not Select.BLANK else "balanced"
        config = UploadConfig(
            obfuscate=self.query_one("#obfuscate", Checkbox).value,
            use_rar=self.query_one("#use-rar", Checkbox).value,
            par_profile=par_profile,
        )
        self.dismiss(config)
