"""
tui_widgets.py

Widgets curses reutilizáveis para o wizard de configuração visual.
Cada widget gerencia seu próprio estado, renderização e validação.
"""

from __future__ import annotations

import curses
import curses.ascii
from abc import ABC, abstractmethod
from typing import Callable, Sequence

# ── Layout ────────────────────────────────────────────────────────────────────

LABEL_WIDTH = 22  # colunas reservadas para o rótulo do campo

# ── Pares de cor (inicializados por init_colors) ──────────────────────────────

CP_NORMAL = 1  # texto padrão
CP_FOCUSED = 2  # campo em foco (fundo azul)
CP_MODIFIED = 3  # valor alterado pelo usuário (amarelo)
CP_ERROR = 4  # erro de validação (fundo vermelho)
CP_DIM = 5  # texto desabilitado / placeholder
CP_SUCCESS = 6  # resultado positivo de teste (verde)
CP_HEADER = 7  # cabeçalho de seção
CP_LABEL = 8  # rótulo de campo (ciano)
CP_SECTION = 9  # separador colapsável


def init_colors() -> None:
    """Inicializa os pares de cor do curses. Deve ser chamado após curses.initscr()."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(CP_NORMAL, curses.COLOR_WHITE, -1)
    curses.init_pair(CP_FOCUSED, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(CP_MODIFIED, curses.COLOR_YELLOW, -1)
    curses.init_pair(CP_ERROR, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(CP_DIM, curses.COLOR_BLACK, -1)
    curses.init_pair(CP_SUCCESS, curses.COLOR_GREEN, -1)
    curses.init_pair(CP_HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(CP_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(CP_SECTION, curses.COLOR_BLUE, -1)


# ── Utilitário de renderização ────────────────────────────────────────────────


def safe_addstr(
    win: curses.window,
    y: int,
    x: int,
    text: str,
    attr: int = 0,
) -> None:
    """Desenha texto recortando nas bordas da janela, sem lançar curses.error."""
    max_y, max_x = win.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    available = max_x - x
    if available <= 0:
        return
    try:
        win.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


# ── Base ──────────────────────────────────────────────────────────────────────


class Widget(ABC):
    """Classe base para todos os widgets do wizard de configuração."""

    def __init__(
        self,
        key: str,
        label: str,
        default: str = "",
        help_text: str = "",
    ) -> None:
        self.key = key
        self.label = label
        self.help_text = help_text
        self._original = default
        self._value = default
        self._error: str | None = None
        self.enabled = True

    # ── Propriedades públicas ──────────────────────────────────────────────

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        self._value = v

    @property
    def dirty(self) -> bool:
        """True se o usuário alterou o valor em relação ao original."""
        return self._value != self._original

    @property
    def error(self) -> str | None:
        return self._error

    # ── API pública ────────────────────────────────────────────────────────

    def validate(self) -> bool:
        """Executa validação; popula self._error. Retorna True se válido."""
        self._error = None
        return True

    def reset(self) -> None:
        """Restaura o valor original e limpa erros."""
        self._value = self._original
        self._error = None

    # ── Métodos abstratos ──────────────────────────────────────────────────

    @abstractmethod
    def height(self) -> int:
        """Número de linhas terminais que o widget ocupa."""
        ...

    @abstractmethod
    def render(
        self,
        win: curses.window,
        y: int,
        x: int,
        width: int,
        focused: bool,
    ) -> None:
        """Desenha o widget. (y, x) é o canto superior esquerdo."""
        ...

    @abstractmethod
    def handle_key(self, key: int) -> bool:
        """Processa tecla; retorna True se consumida."""
        ...


# ── TextField ─────────────────────────────────────────────────────────────────


class TextField(Widget):
    """Campo de texto editável com cursor, scroll e validação inline."""

    def __init__(
        self,
        key: str,
        label: str,
        default: str = "",
        help_text: str = "",
        placeholder: str = "",
        validator: Callable[[str], str | None] | None = None,
        field_width: int = 34,
        secret: bool = False,
    ) -> None:
        super().__init__(key, label, default, help_text)
        self.placeholder = placeholder
        self._validator = validator
        self._field_width = field_width
        self._secret = secret
        self._cursor = len(default)
        self._scroll = 0

    def height(self) -> int:
        return 1

    def _display(self) -> str:
        return "•" * len(self._value) if self._secret else self._value

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        if not self.enabled:
            safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", dim)
            safe_addstr(win, y, x + LABEL_WIDTH, "[ " + " " * self._field_width + " ]", dim)
            return

        safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", curses.color_pair(CP_LABEL))

        fw = min(self._field_width, width - LABEL_WIDTH - 5)
        fx = x + LABEL_WIDTH

        # Atributo do campo
        if self._error:
            box_attr: int = curses.color_pair(CP_ERROR)
        elif focused:
            box_attr = curses.color_pair(CP_FOCUSED)
        elif self.dirty:
            box_attr = curses.color_pair(CP_MODIFIED)
        else:
            box_attr = curses.color_pair(CP_NORMAL)

        shown = self._display()[self._scroll : self._scroll + fw]
        if not shown and not focused and self.placeholder:
            shown = self.placeholder[:fw]
            box_attr = dim

        safe_addstr(win, y, fx, "[ ", curses.color_pair(CP_NORMAL))
        safe_addstr(win, y, fx + 2, f"{shown:<{fw}}", box_attr)
        safe_addstr(win, y, fx + 2 + fw, " ]", curses.color_pair(CP_NORMAL))

        if self.dirty:
            safe_addstr(
                win,
                y,
                fx + fw + 4,
                " *",
                curses.color_pair(CP_MODIFIED) | curses.A_BOLD,
            )
        if self._error:
            safe_addstr(
                win,
                y,
                fx + fw + 7,
                f" ⚠ {self._error}",
                curses.color_pair(CP_ERROR),
            )

        # Posiciona cursor real do terminal
        if focused and not self._secret:
            try:
                win.move(y, fx + 2 + self._cursor - self._scroll)
            except curses.error:
                pass

    def handle_key(self, key: int) -> bool:
        if not self.enabled:
            return False

        if key == curses.KEY_LEFT:
            self._cursor = max(0, self._cursor - 1)
        elif key == curses.KEY_RIGHT:
            self._cursor = min(len(self._value), self._cursor + 1)
        elif key in (curses.KEY_HOME, 1):  # 1 = Ctrl+A
            self._cursor = 0
            self._scroll = 0
        elif key in (curses.KEY_END, 5):  # 5 = Ctrl+E
            self._cursor = len(self._value)
        elif key in (curses.KEY_BACKSPACE, 127, curses.ascii.DEL):
            if self._cursor > 0:
                self._value = self._value[: self._cursor - 1] + self._value[self._cursor :]
                self._cursor -= 1
        elif key == curses.KEY_DC:
            if self._cursor < len(self._value):
                self._value = self._value[: self._cursor] + self._value[self._cursor + 1 :]
        elif key == 11:  # Ctrl+K — apaga até o fim
            self._value = self._value[: self._cursor]
        elif key == 21:  # Ctrl+U — apaga tudo
            self._value = ""
            self._cursor = 0
            self._scroll = 0
        elif 32 <= key < 256:
            self._value = self._value[: self._cursor] + chr(key) + self._value[self._cursor :]
            self._cursor += 1
        else:
            return False

        self._adjust_scroll()
        return True

    def validate(self) -> bool:
        self._error = None
        if not self.enabled:
            return True
        if self._validator:
            self._error = self._validator(self._value)
        return self._error is None

    def _adjust_scroll(self) -> None:
        if self._cursor < self._scroll:
            self._scroll = self._cursor
        elif self._cursor >= self._scroll + self._field_width:
            self._scroll = self._cursor - self._field_width + 1


class PasswordField(TextField):
    """Campo de senha: exibe • em vez do texto real."""

    def __init__(
        self,
        key: str,
        label: str,
        default: str = "",
        help_text: str = "",
        field_width: int = 34,
    ) -> None:
        super().__init__(
            key,
            label,
            default,
            help_text,
            secret=True,
            field_width=field_width,
        )


# ── CheckBox ──────────────────────────────────────────────────────────────────


class CheckBox(Widget):
    """Alternância booleana: [x] / [ ]."""

    def __init__(
        self,
        key: str,
        label: str,
        default: bool = False,
        help_text: str = "",
        description: str = "",
    ) -> None:
        super().__init__(key, label, "true" if default else "false", help_text)
        self._checked = default
        self.description = description

    @property
    def checked(self) -> bool:
        return self._checked

    @property
    def value(self) -> str:
        return "true" if self._checked else "false"

    @value.setter
    def value(self, v: str) -> None:
        self._checked = v.lower() == "true"

    @property
    def dirty(self) -> bool:
        return self.value != self._original

    def height(self) -> int:
        return 1

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        if not self.enabled:
            dim = curses.color_pair(CP_DIM) | curses.A_DIM
            safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}[ ] {self.description}", dim)
            return

        safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", curses.color_pair(CP_LABEL))
        fx = x + LABEL_WIDTH

        mark = "x" if self._checked else " "
        if focused:
            box_attr: int = curses.color_pair(CP_FOCUSED)
        elif self.dirty:
            box_attr = curses.color_pair(CP_MODIFIED)
        else:
            box_attr = curses.color_pair(CP_NORMAL)

        safe_addstr(win, y, fx, f"[{mark}]", box_attr)

        if self.description:
            desc_attr = (
                curses.color_pair(CP_NORMAL)
                if self._checked
                else curses.color_pair(CP_DIM) | curses.A_DIM
            )
            safe_addstr(win, y, fx + 4, self.description, desc_attr)

        if self.dirty:
            desc_end = fx + 4 + len(self.description) + 1
            safe_addstr(win, y, desc_end, "*", curses.color_pair(CP_MODIFIED) | curses.A_BOLD)

    def handle_key(self, key: int) -> bool:
        if not self.enabled:
            return False
        if key in (ord(" "), 10, 13, curses.KEY_ENTER):
            self._checked = not self._checked
            return True
        return False


# ── RadioGroup ────────────────────────────────────────────────────────────────


class RadioOption:
    """Uma opção dentro de um RadioGroup."""

    def __init__(self, value: str, label: str, hint: str = "") -> None:
        self.value = value
        self.label = label
        self.hint = hint  # texto cinza após o rótulo


class RadioGroup(Widget):
    """Grupo de opções mutuamente exclusivas, navegável com ↑↓."""

    def __init__(
        self,
        key: str,
        label: str,
        options: Sequence[RadioOption],
        default: str = "",
        help_text: str = "",
    ) -> None:
        first_val = options[0].value if options else ""
        super().__init__(key, label, default or first_val, help_text)
        self.options = list(options)
        self._selected = next(
            (i for i, o in enumerate(self.options) if o.value == self._original), 0
        )

    @property
    def value(self) -> str:
        return self.options[self._selected].value if self.options else ""

    @value.setter
    def value(self, v: str) -> None:
        idx = next((i for i, o in enumerate(self.options) if o.value == v), None)
        if idx is not None:
            self._selected = idx

    @property
    def dirty(self) -> bool:
        return self.value != self._original

    def height(self) -> int:
        return len(self.options)

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        for i, opt in enumerate(self.options):
            row = y + i
            # Só a primeira linha do grupo exibe o rótulo
            if i == 0:
                safe_addstr(
                    win, row, x, f"{self.label:<{LABEL_WIDTH}}", curses.color_pair(CP_LABEL)
                )
            else:
                safe_addstr(win, row, x, " " * LABEL_WIDTH, 0)

            is_sel = i == self._selected
            mark = "•" if is_sel else " "

            if not self.enabled:
                opt_attr: int = dim
            elif focused and is_sel:
                opt_attr = curses.color_pair(CP_FOCUSED) | curses.A_BOLD
            elif is_sel:
                opt_attr = curses.color_pair(CP_NORMAL) | curses.A_BOLD
            else:
                opt_attr = dim

            radio_str = f"({mark}) {opt.label}"
            safe_addstr(win, row, x + LABEL_WIDTH, radio_str, opt_attr)

            if opt.hint:
                hint_x = x + LABEL_WIDTH + len(radio_str) + 2
                safe_addstr(win, row, hint_x, f"— {opt.hint}", dim)

        if self.dirty:
            safe_addstr(
                win,
                y,
                x + LABEL_WIDTH + 38,
                "*",
                curses.color_pair(CP_MODIFIED) | curses.A_BOLD,
            )

    def handle_key(self, key: int) -> bool:
        if not self.enabled:
            return False
        if key in (curses.KEY_UP,):
            self._selected = (self._selected - 1) % len(self.options)
            return True
        if key in (curses.KEY_DOWN,):
            self._selected = (self._selected + 1) % len(self.options)
            return True
        return False


# ── Slider ────────────────────────────────────────────────────────────────────


class Slider(Widget):
    """Controle numérico com barra visual. ← → ajustam por step; Shift±5×."""

    def __init__(
        self,
        key: str,
        label: str,
        minimum: int,
        maximum: int,
        default: int = 0,
        help_text: str = "",
        step: int = 1,
        bar_width: int = 18,
    ) -> None:
        super().__init__(key, label, str(default), help_text)
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self._bar_width = bar_width
        self._int_value = max(minimum, min(maximum, default))

    @property
    def value(self) -> str:
        return str(self._int_value)

    @value.setter
    def value(self, v: str) -> None:
        try:
            self._int_value = max(self.minimum, min(self.maximum, int(v)))
        except ValueError:
            pass

    @property
    def dirty(self) -> bool:
        try:
            return self._int_value != int(self._original)
        except ValueError:
            return False

    def height(self) -> int:
        return 1

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        if not self.enabled:
            safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", dim)
            return

        safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", curses.color_pair(CP_LABEL))
        fx = x + LABEL_WIDTH

        ratio = (self._int_value - self.minimum) / max(1, self.maximum - self.minimum)
        filled = round(ratio * self._bar_width)
        bar = "█" * filled + "░" * (self._bar_width - filled)

        if focused:
            arrow_attr: int = curses.color_pair(CP_FOCUSED) | curses.A_BOLD
            bar_attr: int = curses.color_pair(CP_FOCUSED)
        elif self.dirty:
            arrow_attr = curses.color_pair(CP_MODIFIED) | curses.A_BOLD
            bar_attr = curses.color_pair(CP_MODIFIED)
        else:
            arrow_attr = curses.color_pair(CP_NORMAL)
            bar_attr = curses.color_pair(CP_NORMAL)

        safe_addstr(win, y, fx, "◄ ", arrow_attr)
        safe_addstr(win, y, fx + 2, bar, bar_attr)
        safe_addstr(win, y, fx + 2 + self._bar_width, " ►", arrow_attr)
        safe_addstr(
            win,
            y,
            fx + self._bar_width + 5,
            f" {self._int_value:<4}",
            curses.color_pair(CP_NORMAL) | curses.A_BOLD,
        )
        if self.dirty:
            safe_addstr(
                win,
                y,
                fx + self._bar_width + 11,
                "*",
                curses.color_pair(CP_MODIFIED) | curses.A_BOLD,
            )

    def handle_key(self, key: int) -> bool:
        if not self.enabled:
            return False
        big = self.step * 5
        if key == curses.KEY_LEFT:
            self._int_value = max(self.minimum, self._int_value - self.step)
        elif key == curses.KEY_RIGHT:
            self._int_value = min(self.maximum, self._int_value + self.step)
        elif key == curses.KEY_SLEFT:  # Shift+←
            self._int_value = max(self.minimum, self._int_value - big)
        elif key == curses.KEY_SRIGHT:  # Shift+→
            self._int_value = min(self.maximum, self._int_value + big)
        else:
            return False
        return True


# ── Dropdown ──────────────────────────────────────────────────────────────────


class Dropdown(Widget):
    """Lista de opções fechada; Enter/Espaço abre; ↑↓ selecionam; Esc fecha."""

    def __init__(
        self,
        key: str,
        label: str,
        options: Sequence[tuple[str, str]],  # (valor, rótulo_exibido)
        default: str = "",
        help_text: str = "",
    ) -> None:
        first_val = options[0][0] if options else ""
        super().__init__(key, label, default or first_val, help_text)
        self.options = list(options)
        self._selected = next(
            (i for i, (v, _) in enumerate(self.options) if v == self._original), 0
        )
        self._open = False

    @property
    def value(self) -> str:
        return self.options[self._selected][0] if self.options else ""

    @value.setter
    def value(self, v: str) -> None:
        idx = next((i for i, (val, _) in enumerate(self.options) if val == v), None)
        if idx is not None:
            self._selected = idx

    @property
    def dirty(self) -> bool:
        return self.value != self._original

    def height(self) -> int:
        return 1 + len(self.options) if self._open else 1

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        safe_addstr(win, y, x, f"{self.label:<{LABEL_WIDTH}}", curses.color_pair(CP_LABEL))
        fx = x + LABEL_WIDTH

        display = self.options[self._selected][1] if self.options else ""
        arrow = "▾" if self._open else "▸"

        if not self.enabled:
            safe_addstr(win, y, fx, f"[ {display:<22}{arrow}]", dim)
            return

        if self._open or focused:
            hdr_attr: int = curses.color_pair(CP_FOCUSED) | curses.A_BOLD
        elif self.dirty:
            hdr_attr = curses.color_pair(CP_MODIFIED)
        else:
            hdr_attr = curses.color_pair(CP_NORMAL)

        safe_addstr(win, y, fx, f"[ {display:<22}{arrow}]", hdr_attr)

        if self.dirty and not self._open:
            safe_addstr(win, y, fx + 27, "*", curses.color_pair(CP_MODIFIED) | curses.A_BOLD)

        if self._open:
            for i, (_, lbl) in enumerate(self.options):
                row = y + 1 + i
                if i == self._selected:
                    safe_addstr(
                        win,
                        row,
                        fx + 2,
                        f"▸ {lbl:<22}",
                        curses.color_pair(CP_FOCUSED) | curses.A_BOLD,
                    )
                else:
                    safe_addstr(win, row, fx + 2, f"  {lbl:<22}", curses.color_pair(CP_NORMAL))

    def handle_key(self, key: int) -> bool:
        if not self.enabled:
            return False
        if key in (ord(" "), 10, 13, curses.KEY_ENTER):
            self._open = not self._open
            return True
        if self._open:
            if key == curses.KEY_UP:
                self._selected = (self._selected - 1) % len(self.options)
                return True
            if key == curses.KEY_DOWN:
                self._selected = (self._selected + 1) % len(self.options)
                return True
            if key == 27:  # Esc fecha sem mudar
                self._open = False
                return True
        else:
            # Atalho sem abrir: ←→ ciclam entre opções
            if key == curses.KEY_LEFT:
                self._selected = (self._selected - 1) % len(self.options)
                return True
            if key == curses.KEY_RIGHT:
                self._selected = (self._selected + 1) % len(self.options)
                return True
        return False


# ── Button ────────────────────────────────────────────────────────────────────


class Button(Widget):
    """Botão de ação inline. Exibe resultado (✓/✗) após execução."""

    def __init__(
        self,
        label: str,
        action: Callable[[], tuple[bool, str]],
        help_text: str = "",
    ) -> None:
        # action() → (sucesso: bool, mensagem: str)
        super().__init__("", label, "", help_text)
        self._action = action
        self._result: tuple[bool, str] | None = None

    @property
    def dirty(self) -> bool:
        return False

    def height(self) -> int:
        return 1

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        fx = x + LABEL_WIDTH
        attr = (
            curses.color_pair(CP_FOCUSED) | curses.A_BOLD
            if focused
            else curses.color_pair(CP_NORMAL) | curses.A_BOLD
        )
        safe_addstr(win, y, fx, f"[ {self.label} ]", attr)

        if self._result is not None:
            ok, msg = self._result
            result_attr = (
                curses.color_pair(CP_SUCCESS) | curses.A_BOLD
                if ok
                else curses.color_pair(CP_ERROR) | curses.A_BOLD
            )
            icon = "✓" if ok else "✗"
            safe_addstr(win, y, fx + len(self.label) + 5, f"  {icon} {msg}", result_attr)

    def handle_key(self, key: int) -> bool:
        if key in (ord(" "), 10, 13, curses.KEY_ENTER):
            self._result = self._action()
            return True
        return False

    def clear_result(self) -> None:
        self._result = None


# ── SectionHeader ─────────────────────────────────────────────────────────────


class SectionHeader(Widget):
    """Separador visual entre grupos de campos. Não recebe foco."""

    def __init__(self, title: str) -> None:
        super().__init__("", title, "", "")

    @property
    def dirty(self) -> bool:
        return False

    def height(self) -> int:
        return 1

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        bar = "─" * max(0, width - len(self.label) - 4)
        safe_addstr(
            win,
            y,
            x,
            f"  {self.label} {bar}",
            curses.color_pair(CP_SECTION) | curses.A_BOLD,
        )

    def handle_key(self, key: int) -> bool:
        return False


# ── CollapsibleSection ────────────────────────────────────────────────────────


class CollapsibleSection(Widget):
    """Seção expansível/recolhível. Enter/Espaço alterna estado."""

    def __init__(
        self,
        title: str,
        children: list[Widget],
        expanded: bool = False,
    ) -> None:
        super().__init__("", title, "", "")
        self.children = children
        self._expanded = expanded

    @property
    def expanded(self) -> bool:
        return self._expanded

    @property
    def dirty(self) -> bool:
        return any(c.dirty for c in self.children)

    def height(self) -> int:
        base = 1
        if self._expanded:
            base += sum(c.height() for c in self.children)
        return base

    def render(self, win: curses.window, y: int, x: int, width: int, focused: bool) -> None:
        arrow = "▾" if self._expanded else "▸"
        dirty_mark = " *" if self.dirty else ""
        attr = (
            curses.color_pair(CP_FOCUSED) | curses.A_BOLD
            if focused
            else curses.color_pair(CP_SECTION) | curses.A_BOLD
        )
        safe_addstr(win, y, x, f"  {arrow} {self.label}{dirty_mark}", attr)

        if self._expanded:
            row = y + 1
            for child in self.children:
                child.render(win, row, x + 4, width - 4, False)
                row += child.height()

    def handle_key(self, key: int) -> bool:
        if key in (ord(" "), 10, 13, curses.KEY_ENTER):
            self._expanded = not self._expanded
            return True
        return False


# ── HelpPanel ─────────────────────────────────────────────────────────────────


class HelpPanel:
    """Painel lateral de ajuda contextual. Renderiza à direita do formulário."""

    _PANEL_WIDTH = 28

    def __init__(self) -> None:
        self._text = ""
        self._title = ""

    @property
    def width(self) -> int:
        return self._PANEL_WIDTH

    def set(self, title: str, text: str) -> None:
        self._title = title
        self._text = text

    def render(self, win: curses.window, y: int, x: int, height: int) -> None:
        w = self._PANEL_WIDTH
        border = curses.color_pair(CP_SECTION)
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        normal = curses.color_pair(CP_NORMAL)

        # Borda superior
        safe_addstr(win, y, x, "┌" + "─" * (w - 2) + "┐", border)

        # Título
        title = self._title[: w - 4]
        safe_addstr(win, y + 1, x, "│ ", border)
        safe_addstr(
            win, y + 1, x + 2, f"{title:<{w - 4}}", curses.color_pair(CP_LABEL) | curses.A_BOLD
        )
        safe_addstr(win, y + 1, x + w - 2, " │", border)

        # Separador
        safe_addstr(win, y + 2, x, "├" + "─" * (w - 2) + "┤", border)

        # Conteúdo — quebra linhas longas automaticamente
        lines = self._wrap(self._text, w - 4)
        row = y + 3
        for line in lines:
            if row >= y + height - 1:
                break
            safe_addstr(win, row, x, "│ ", border)
            safe_addstr(win, row, x + 2, f"{line:<{w - 4}}", normal if line.strip() else dim)
            safe_addstr(win, row, x + w - 2, " │", border)
            row += 1

        # Preenche linhas vazias
        while row < y + height - 1:
            safe_addstr(win, row, x, "│" + " " * (w - 2) + "│", border)
            row += 1

        # Borda inferior
        safe_addstr(win, y + height - 1, x, "└" + "─" * (w - 2) + "┘", border)

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        """Quebra texto em linhas de no máximo `width` caracteres."""
        result: list[str] = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                result.append("")
                continue
            words = paragraph.split()
            line = ""
            for word in words:
                if len(line) + len(word) + (1 if line else 0) <= width:
                    line = f"{line} {word}" if line else word
                else:
                    result.append(line)
                    line = word
            if line:
                result.append(line)
        return result


# ── FormPage ──────────────────────────────────────────────────────────────────


class FormPage:
    """
    Container de widgets com navegação por Tab/↑↓.

    Gerencia o índice de foco, scroll vertical e coleta de valores alterados.
    CollapsibleSection e SectionHeader não recebem foco diretamente;
    a seção colapsável é focada como um widget normal e Enter abre/fecha.
    """

    def __init__(self, widgets: list[Widget]) -> None:
        self._widgets = widgets
        self._focus_idx = 0

    # ── Foco ──────────────────────────────────────────────────────────────

    @property
    def _focusable(self) -> list[Widget]:
        """Widgets que recebem foco (exclui SectionHeader não interativo)."""
        return [w for w in self._widgets if not isinstance(w, SectionHeader)]

    @property
    def focused_widget(self) -> Widget | None:
        f = self._focusable
        return f[self._focus_idx % len(f)] if f else None

    def next_focus(self) -> None:
        f = self._focusable
        if f:
            self._focus_idx = (self._focus_idx + 1) % len(f)

    def prev_focus(self) -> None:
        f = self._focusable
        if f:
            self._focus_idx = (self._focus_idx - 1) % len(f)

    # ── Renderização ──────────────────────────────────────────────────────

    def render(
        self,
        win: curses.window,
        y: int,
        x: int,
        width: int,
        height: int,
        scroll_top: int = 0,
    ) -> None:
        """Desenha os widgets a partir de scroll_top, recortando em height linhas."""
        current = self.focused_widget
        row = y
        virtual_row = 0  # linha lógica antes do scroll

        for widget in self._widgets:
            h = widget.height()
            if virtual_row + h <= scroll_top:
                virtual_row += h
                continue
            if row - y >= height:
                break

            focused = widget is current
            draw_y = row - max(0, scroll_top - virtual_row)
            widget.render(win, draw_y, x, width, focused)
            row += h
            virtual_row += h

    def total_height(self) -> int:
        return sum(w.height() for w in self._widgets)

    # ── Teclado ───────────────────────────────────────────────────────────

    def handle_key(self, key: int) -> bool:
        """Repassa a tecla ao widget focado; Tab/↑↓ navegam entre widgets."""
        focused = self.focused_widget
        if focused and focused.handle_key(key):
            return True
        if key == 9:  # Tab
            self.next_focus()
            return True
        if key == curses.KEY_BTAB:  # Shift+Tab
            self.prev_focus()
            return True
        return False

    # ── Coleta e validação ────────────────────────────────────────────────

    def collect_values(self) -> dict[str, str]:
        """Retorna apenas os campos modificados pelo usuário."""
        result: dict[str, str] = {}
        for w in self._widgets:
            if isinstance(w, CollapsibleSection):
                for child in w.children:
                    if child.key and child.dirty:
                        result[child.key] = child.value
            elif w.key and w.dirty:
                result[w.key] = w.value
        return result

    def validate_all(self) -> list[str]:
        """Valida todos os campos; retorna lista de mensagens de erro."""
        errors: list[str] = []
        for w in self._widgets:
            targets: list[Widget] = w.children if isinstance(w, CollapsibleSection) else [w]
            for t in targets:
                if not t.validate() and t.error:
                    errors.append(f"{t.label}: {t.error}")
        return errors

    def load_values(self, env: dict[str, str]) -> None:
        """Popula os widgets com valores vindos de um .env carregado."""
        for w in self._widgets:
            targets: list[Widget] = w.children if isinstance(w, CollapsibleSection) else [w]
            for t in targets:
                if t.key and t.key in env:
                    t.value = env[t.key]
                    t._original = env[t.key]  # não marca como dirty ao carregar


__all__ = [
    "init_colors",
    "safe_addstr",
    "LABEL_WIDTH",
    "CP_NORMAL",
    "CP_FOCUSED",
    "CP_MODIFIED",
    "CP_ERROR",
    "CP_DIM",
    "CP_SUCCESS",
    "CP_HEADER",
    "CP_LABEL",
    "CP_SECTION",
    "Widget",
    "TextField",
    "PasswordField",
    "CheckBox",
    "RadioOption",
    "RadioGroup",
    "Slider",
    "Dropdown",
    "Button",
    "SectionHeader",
    "CollapsibleSection",
    "HelpPanel",
    "FormPage",
]
