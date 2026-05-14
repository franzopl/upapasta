"""
tui/screens/pattern_select.py

Modal de seleção inteligente por padrão.
Oferece opções predefinidas (status, tamanho, temporada) além de regex livre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Union

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class RuleKind(Enum):
    STATUS_PENDING = auto()
    STATUS_FAILED = auto()
    MIN_SIZE_GB = auto()
    SEASON_PATTERN = auto()
    REGEX = auto()


@dataclass
class SelectionRule:
    kind: RuleKind
    # Para MIN_SIZE_GB: valor em bytes; para REGEX: string do padrão
    value: Union[int, str, None] = None


class PatternSelectScreen(ModalScreen[Optional[SelectionRule]]):
    """Modal de seleção inteligente. Retorna um SelectionRule ou None se cancelado."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
    ]

    DEFAULT_CSS = """
    PatternSelectScreen {
        align: center middle;
    }

    #dialog {
        background: $surface;
        border: thick $warning;
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 30;
    }

    .title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    .subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #preset-buttons {
        height: auto;
        margin-bottom: 1;
    }

    Button {
        width: 1fr;
        margin-bottom: 0;
    }

    #size-row {
        height: 3;
        margin-top: 1;
        align: left middle;
        display: none;
    }

    #size-label {
        width: auto;
        padding: 0 1 0 0;
    }

    #size-input {
        width: 10;
    }

    #regex-row {
        height: 3;
        margin-top: 1;
        display: none;
    }

    #regex-input {
        width: 1fr;
    }

    #confirm-row {
        height: auto;
        align: right middle;
        margin-top: 1;
        display: none;
    }

    Button.confirm-btn {
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._pending_kind: Optional[RuleKind] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Selecionar por Padrão", classes="title")
            yield Static(
                "Escolha uma opção para selecionar itens automaticamente:", classes="subtitle"
            )

            with Vertical(id="preset-buttons"):
                yield Button(
                    "❌  Todos PENDING (não enviados) nesta pasta",
                    id="btn-pending",
                    variant="default",
                )
                yield Button(
                    "🔄  Todos FAILED (com falha) nesta pasta",
                    id="btn-failed",
                    variant="default",
                )
                yield Button(
                    "📦  Arquivos com tamanho > X GB",
                    id="btn-size",
                    variant="default",
                )
                yield Button(
                    "📺  Pastas de temporada  (ex: S01, S02…)",
                    id="btn-season",
                    variant="default",
                )
                yield Button(
                    "🔍  Regex personalizado",
                    id="btn-regex",
                    variant="default",
                )

            with Horizontal(id="size-row"):
                yield Static("Tamanho mínimo (GB):", id="size-label")
                yield Input(placeholder="ex: 10", id="size-input")

            with Horizontal(id="regex-row"):
                yield Input(placeholder="ex: .*S0[1-3].*", id="regex-input")

            with Horizontal(id="confirm-row"):
                yield Button(
                    "Cancelar", variant="default", id="btn-cancel-sub", classes="confirm-btn"
                )
                yield Button("Aplicar", variant="primary", id="btn-apply", classes="confirm-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "btn-pending":
            self.dismiss(SelectionRule(kind=RuleKind.STATUS_PENDING))
        elif bid == "btn-failed":
            self.dismiss(SelectionRule(kind=RuleKind.STATUS_FAILED))
        elif bid == "btn-season":
            self.dismiss(SelectionRule(kind=RuleKind.SEASON_PATTERN))
        elif bid == "btn-size":
            self._show_sub_input("size")
        elif bid == "btn-regex":
            self._show_sub_input("regex")
        elif bid == "btn-cancel-sub":
            self._hide_sub_inputs()
        elif bid == "btn-apply":
            self._apply_sub_input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._apply_sub_input()

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _show_sub_input(self, kind: str) -> None:
        self.query_one("#size-row").display = kind == "size"
        self.query_one("#regex-row").display = kind == "regex"
        self.query_one("#confirm-row").display = True
        self._pending_kind = RuleKind.MIN_SIZE_GB if kind == "size" else RuleKind.REGEX
        if kind == "size":
            self.query_one("#size-input", Input).focus()
        else:
            self.query_one("#regex-input", Input).focus()

    def _hide_sub_inputs(self) -> None:
        self.query_one("#size-row").display = False
        self.query_one("#regex-row").display = False
        self.query_one("#confirm-row").display = False
        self._pending_kind = None

    def _apply_sub_input(self) -> None:
        if self._pending_kind == RuleKind.MIN_SIZE_GB:
            raw = self.query_one("#size-input", Input).value.strip()
            try:
                gb = float(raw)
                if gb <= 0:
                    raise ValueError
            except ValueError:
                self.app.notify("Digite um número positivo de GB.", severity="error")
                return
            self.dismiss(SelectionRule(kind=RuleKind.MIN_SIZE_GB, value=int(gb * 1024**3)))

        elif self._pending_kind == RuleKind.REGEX:
            pattern = self.query_one("#regex-input", Input).value.strip()
            if not pattern:
                self.app.notify("Digite um padrão regex.", severity="error")
                return
            try:
                re.compile(pattern, re.I)
            except re.error as exc:
                self.app.notify(f"Regex inválido: {exc}", severity="error")
                return
            self.dismiss(SelectionRule(kind=RuleKind.REGEX, value=pattern))
