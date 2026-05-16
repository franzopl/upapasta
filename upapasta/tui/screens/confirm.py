"""
tui/screens/confirm.py

Modal de confirmação pré-upload: exibe itens selecionados e permite escolher
as opções de upload (ofuscação, compactação, senha, modo, perfil PAR2) antes
de iniciar.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from ..fs_scanner import FileNode, _fmt_size

# Valores válidos do campo de compactação.
_COMPRESSION_NONE = "none"
_COMPRESSION_RAR = "rar"
_COMPRESSION_7Z = "7z"


@dataclass
class UploadConfig:
    """Opções de upload escolhidas no modal de confirmação."""

    obfuscate: bool
    par_profile: str
    # "none" | "rar" | "7z"
    compression: str = _COMPRESSION_NONE
    # Quando use_password é True e password é vazio, gera senha aleatória.
    use_password: bool = False
    password: str = ""
    # Processa cada arquivo da pasta como um release separado (--each).
    each: bool = False

    @property
    def use_rar(self) -> bool:
        """Compat: True se a compactação escolhida for RAR."""
        return self.compression == _COMPRESSION_RAR

    @property
    def use_7z(self) -> bool:
        """True se a compactação escolhida for 7z."""
        return self.compression == _COMPRESSION_7Z


def build_upload_cmd(item: FileNode, config: UploadConfig) -> list[str]:
    """
    Constrói o comando CLI para um item com as opções dadas.

    O modo porcelain é ativado pelo UploadPanel via env UPAPASTA_PORCELAIN=1,
    não por flag — mantém a linha de comando exibida no log limpa.
    """
    cmd = [sys.executable, "-m", "upapasta", str(item.path)]
    if config.obfuscate:
        cmd.append("--obfuscate")
    if config.compression == _COMPRESSION_RAR:
        cmd.append("--rar")
    elif config.compression == _COMPRESSION_7Z:
        cmd.append("--7z")
    if config.use_password:
        if config.password:
            cmd.extend(["--password", config.password])
        else:
            # Sem argumento → a CLI gera uma senha aleatória de 16 caracteres.
            cmd.append("--password")
    if config.each:
        cmd.append("--each")
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
        width: 74;
        height: auto;
        max-height: 95%;
        overflow-y: auto;
        scrollbar-gutter: stable;
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
        max-height: 8;
        margin-bottom: 1;
        overflow-y: auto;
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

    .opt-row {
        height: 3;
        align: left middle;
        margin-top: 0;
    }

    .opt-label {
        width: 16;
        padding: 1 1 0 0;
    }

    #compression, #par-profile {
        width: 22;
    }

    #password-input {
        width: 1fr;
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
        has_dir = any(n.is_dir for n in self._items)

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
                yield Checkbox("Ofuscar nomes de arquivos  (--obfuscate)", id="obfuscate")

                with Horizontal(classes="opt-row"):
                    yield Static("Compactação:", classes="opt-label")
                    yield Select(
                        [
                            ("Nenhuma (upload direto)", _COMPRESSION_NONE),
                            ("RAR5", _COMPRESSION_RAR),
                            ("7z", _COMPRESSION_7Z),
                        ],
                        value=_COMPRESSION_NONE,
                        allow_blank=False,
                        id="compression",
                    )

                yield Checkbox("Proteger com senha  (compacta automaticamente)", id="use-password")
                with Horizontal(classes="opt-row"):
                    yield Static("Senha:", classes="opt-label")
                    yield Input(
                        placeholder="vazio = gerar senha aleatória de 16 caracteres",
                        id="password-input",
                        disabled=True,
                    )

                # --each só faz sentido quando há pelo menos uma pasta selecionada.
                if has_dir:
                    yield Checkbox("Cada arquivo da pasta vira um release  (--each)", id="each")

                with Horizontal(classes="opt-row"):
                    yield Static("Perfil PAR2:", classes="opt-label")
                    yield Select(
                        [("fast", "fast"), ("balanced", "balanced"), ("safe", "safe")],
                        value="balanced",
                        allow_blank=False,
                        id="par-profile",
                    )

            with Horizontal(id="buttons"):
                yield Button("Cancelar", variant="default", id="btn-cancel")
                yield Button("Iniciar upload", variant="primary", id="btn-confirm")

    def on_mount(self) -> None:
        self._update_par_estimate()

    def on_select_changed(self) -> None:
        self._update_par_estimate()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Habilita o campo de senha somente quando 'Proteger com senha' está marcado."""
        if event.checkbox.id == "use-password":
            self.query_one("#password-input", Input).disabled = not event.value

    def _update_par_estimate(self) -> None:
        total_bytes = sum(n.size for n in self._items if not n.is_dir)
        if total_bytes == 0:
            return
        profile = self._selected_profile()
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

    # ── Internals ─────────────────────────────────────────────────────────────

    def _selected_profile(self) -> str:
        val = self.query_one("#par-profile", Select).value
        return str(val) if val is not Select.BLANK else "balanced"

    def _selected_compression(self) -> str:
        val = self.query_one("#compression", Select).value
        return str(val) if val is not Select.BLANK else _COMPRESSION_NONE

    def _dismiss_with_config(self) -> None:
        try:
            each = self.query_one("#each", Checkbox).value
        except NoMatches:
            each = False  # checkbox ausente quando nenhum item é pasta
        config = UploadConfig(
            obfuscate=self.query_one("#obfuscate", Checkbox).value,
            par_profile=self._selected_profile(),
            compression=self._selected_compression(),
            use_password=self.query_one("#use-password", Checkbox).value,
            password=self.query_one("#password-input", Input).value.strip(),
            each=each,
        )
        self.dismiss(config)
