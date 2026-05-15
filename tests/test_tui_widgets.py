"""
Testes dos widgets curses do wizard de configuração.

Não requer terminal real — testa apenas lógica de estado, navegação,
validação e coleta de valores. Renderização é exercida via MockWin.
"""

from __future__ import annotations

import curses
from typing import Any

import pytest


# curses.color_pair exige initscr() — mockamos para não precisar de terminal
@pytest.fixture(autouse=True)
def _mock_curses_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "color_pair", lambda n: 0)


from upapasta.tui_widgets import (
    Button,
    CheckBox,
    CollapsibleSection,
    Dropdown,
    FormPage,
    HelpPanel,
    PasswordField,
    RadioGroup,
    RadioOption,
    SectionHeader,
    Slider,
    TextField,
)

# ── Fixture: janela curses falsa ──────────────────────────────────────────────


class MockWin:
    """Janela curses mínima para exercitar render() sem terminal real."""

    def __init__(self, rows: int = 40, cols: int = 120) -> None:
        self._rows = rows
        self._cols = cols
        self.calls: list[tuple[str, Any]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def addstr(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("addstr", args))

    def move(self, *args: Any) -> None:
        self.calls.append(("move", args))

    def erase(self) -> None:
        pass

    def refresh(self) -> None:
        pass

    def getch(self) -> int:
        return ord("q")

    def keypad(self, *args: Any) -> None:
        pass


@pytest.fixture()
def win() -> MockWin:
    return MockWin()


# ── TextField ─────────────────────────────────────────────────────────────────


class TestTextField:
    def test_initial_value(self) -> None:
        tf = TextField("K", "Label", default="hello")
        assert tf.value == "hello"

    def test_not_dirty_initially(self) -> None:
        tf = TextField("K", "Label", default="abc")
        assert not tf.dirty

    def test_typing_makes_dirty(self) -> None:
        tf = TextField("K", "Label", default="")
        tf.handle_key(ord("x"))
        assert tf.dirty
        assert tf.value == "x"

    def test_insert_at_cursor(self) -> None:
        tf = TextField("K", "Label", default="ac")
        tf._cursor = 1
        tf.handle_key(ord("b"))
        assert tf.value == "abc"

    def test_backspace(self) -> None:
        tf = TextField("K", "Label", default="ab")
        tf._cursor = 2
        tf.handle_key(curses.KEY_BACKSPACE)
        assert tf.value == "a"
        assert tf._cursor == 1

    def test_delete_key(self) -> None:
        tf = TextField("K", "Label", default="ab")
        tf._cursor = 0
        tf.handle_key(curses.KEY_DC)
        assert tf.value == "b"

    def test_home_end(self) -> None:
        tf = TextField("K", "Label", default="hello")
        tf._cursor = 3
        tf.handle_key(curses.KEY_HOME)
        assert tf._cursor == 0
        tf.handle_key(curses.KEY_END)
        assert tf._cursor == 5

    def test_ctrl_k_clears_to_end(self) -> None:
        tf = TextField("K", "Label", default="hello")
        tf._cursor = 2
        tf.handle_key(11)  # Ctrl+K
        assert tf.value == "he"

    def test_ctrl_u_clears_all(self) -> None:
        tf = TextField("K", "Label", default="hello")
        tf.handle_key(21)  # Ctrl+U
        assert tf.value == ""
        assert tf._cursor == 0

    def test_left_right_clamped(self) -> None:
        tf = TextField("K", "Label", default="ab")
        tf._cursor = 0
        tf.handle_key(curses.KEY_LEFT)
        assert tf._cursor == 0
        tf._cursor = 2
        tf.handle_key(curses.KEY_RIGHT)
        assert tf._cursor == 2

    def test_reset(self) -> None:
        tf = TextField("K", "Label", default="orig")
        tf.handle_key(ord("x"))
        tf.reset()
        assert tf.value == "orig"
        assert not tf.dirty

    def test_validator_called(self) -> None:
        tf = TextField("K", "L", validator=lambda v: "bad" if v == "x" else None)
        tf._value = "x"
        assert not tf.validate()
        assert tf.error == "bad"

    def test_validator_clears_on_valid(self) -> None:
        tf = TextField("K", "L", validator=lambda v: None)
        tf._value = "ok"
        assert tf.validate()
        assert tf.error is None

    def test_disabled_ignores_keys(self) -> None:
        tf = TextField("K", "L", default="x")
        tf.enabled = False
        assert not tf.handle_key(ord("a"))
        assert tf.value == "x"

    def test_render_does_not_raise(self, win: MockWin) -> None:
        tf = TextField("K", "Label", default="hello")
        tf.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]
        assert any(c[0] == "addstr" for c in win.calls)

    def test_scroll_adjusts_on_long_text(self) -> None:
        tf = TextField("K", "L", default="", field_width=5)
        for ch in "abcdefghij":
            tf.handle_key(ord(ch))
        # Cursor está no fim (10), scroll deve ser > 0
        assert tf._scroll > 0
        assert tf._cursor == 10


# ── PasswordField ─────────────────────────────────────────────────────────────


class TestPasswordField:
    def test_display_masks_value(self) -> None:
        pf = PasswordField("P", "Senha", default="secret")
        assert pf._display() == "••••••"

    def test_value_stored_plaintext(self) -> None:
        pf = PasswordField("P", "Senha", default="")
        pf.handle_key(ord("p"))
        assert pf.value == "p"

    def test_inherits_dirty(self) -> None:
        pf = PasswordField("P", "Senha", default="orig")
        assert not pf.dirty
        pf.handle_key(ord("x"))
        assert pf.dirty


# ── CheckBox ──────────────────────────────────────────────────────────────────


class TestCheckBox:
    def test_initial_false(self) -> None:
        cb = CheckBox("K", "L", default=False)
        assert cb.value == "false"
        assert not cb.checked

    def test_initial_true(self) -> None:
        cb = CheckBox("K", "L", default=True)
        assert cb.value == "true"
        assert cb.checked

    def test_space_toggles(self) -> None:
        cb = CheckBox("K", "L", default=False)
        cb.handle_key(ord(" "))
        assert cb.checked
        cb.handle_key(ord(" "))
        assert not cb.checked

    def test_enter_toggles(self) -> None:
        cb = CheckBox("K", "L", default=False)
        cb.handle_key(10)
        assert cb.checked

    def test_dirty_after_toggle(self) -> None:
        cb = CheckBox("K", "L", default=False)
        assert not cb.dirty
        cb.handle_key(ord(" "))
        assert cb.dirty

    def test_not_dirty_after_double_toggle(self) -> None:
        cb = CheckBox("K", "L", default=True)
        cb.handle_key(ord(" "))
        cb.handle_key(ord(" "))
        assert not cb.dirty

    def test_disabled_ignores_toggle(self) -> None:
        cb = CheckBox("K", "L", default=False)
        cb.enabled = False
        cb.handle_key(ord(" "))
        assert not cb.checked

    def test_render_does_not_raise(self, win: MockWin) -> None:
        cb = CheckBox("K", "Label", default=True)
        cb.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── RadioGroup ────────────────────────────────────────────────────────────────


class TestRadioGroup:
    def _make(self, default: str = "a") -> RadioGroup:
        return RadioGroup(
            "K",
            "Label",
            [RadioOption("a", "A"), RadioOption("b", "B"), RadioOption("c", "C")],
            default=default,
        )

    def test_initial_value(self) -> None:
        rg = self._make("b")
        assert rg.value == "b"

    def test_down_cycles(self) -> None:
        rg = self._make("a")
        rg.handle_key(curses.KEY_DOWN)
        assert rg.value == "b"

    def test_up_wraps(self) -> None:
        rg = self._make("a")
        rg.handle_key(curses.KEY_UP)
        assert rg.value == "c"

    def test_down_wraps(self) -> None:
        rg = self._make("c")
        rg.handle_key(curses.KEY_DOWN)
        assert rg.value == "a"

    def test_dirty_on_change(self) -> None:
        rg = self._make("a")
        assert not rg.dirty
        rg.handle_key(curses.KEY_DOWN)
        assert rg.dirty

    def test_not_dirty_if_back_to_original(self) -> None:
        rg = self._make("a")
        rg.handle_key(curses.KEY_DOWN)
        rg.handle_key(curses.KEY_UP)
        assert not rg.dirty

    def test_height_equals_option_count(self) -> None:
        rg = self._make()
        assert rg.height() == 3

    def test_disabled_ignores_navigation(self) -> None:
        rg = self._make("a")
        rg.enabled = False
        rg.handle_key(curses.KEY_DOWN)
        assert rg.value == "a"

    def test_render_does_not_raise(self, win: MockWin) -> None:
        rg = self._make("a")
        rg.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── Slider ────────────────────────────────────────────────────────────────────


class TestSlider:
    def test_initial_value(self) -> None:
        s = Slider("K", "L", minimum=1, maximum=100, default=50)
        assert s.value == "50"

    def test_right_increments(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=5)
        s.handle_key(curses.KEY_RIGHT)
        assert s.value == "6"

    def test_left_decrements(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=5)
        s.handle_key(curses.KEY_LEFT)
        assert s.value == "4"

    def test_clamps_at_max(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=10)
        s.handle_key(curses.KEY_RIGHT)
        assert s.value == "10"

    def test_clamps_at_min(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=0)
        s.handle_key(curses.KEY_LEFT)
        assert s.value == "0"

    def test_shift_right_big_step(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=100, default=0, step=1)
        s.handle_key(curses.KEY_SRIGHT)
        assert s.value == "5"

    def test_shift_left_big_step(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=100, default=50, step=1)
        s.handle_key(curses.KEY_SLEFT)
        assert s.value == "45"

    def test_dirty_on_change(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=5)
        assert not s.dirty
        s.handle_key(curses.KEY_RIGHT)
        assert s.dirty

    def test_value_setter(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=100, default=0)
        s.value = "42"
        assert s._int_value == 42

    def test_value_setter_clamps(self) -> None:
        s = Slider("K", "L", minimum=0, maximum=10, default=5)
        s.value = "999"
        assert s._int_value == 10

    def test_render_does_not_raise(self, win: MockWin) -> None:
        s = Slider("K", "Label", minimum=0, maximum=100, default=50)
        s.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── Dropdown ──────────────────────────────────────────────────────────────────


class TestDropdown:
    def _make(self, default: str = "a") -> Dropdown:
        return Dropdown(
            "K",
            "Label",
            [("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            default=default,
        )

    def test_initial_value(self) -> None:
        d = self._make("b")
        assert d.value == "b"

    def test_left_right_cycle_closed(self) -> None:
        d = self._make("a")
        d.handle_key(curses.KEY_RIGHT)
        assert d.value == "b"
        d.handle_key(curses.KEY_LEFT)
        assert d.value == "a"

    def test_enter_opens(self) -> None:
        d = self._make("a")
        d.handle_key(10)
        assert d._open

    def test_enter_closes_when_open(self) -> None:
        d = self._make("a")
        d._open = True
        d.handle_key(10)
        assert not d._open

    def test_esc_closes(self) -> None:
        d = self._make("a")
        d._open = True
        d.handle_key(27)
        assert not d._open

    def test_down_when_open(self) -> None:
        d = self._make("a")
        d._open = True
        d.handle_key(curses.KEY_DOWN)
        assert d.value == "b"

    def test_up_when_open(self) -> None:
        d = self._make("b")
        d._open = True
        d.handle_key(curses.KEY_UP)
        assert d.value == "a"

    def test_height_closed(self) -> None:
        d = self._make()
        assert d.height() == 1

    def test_height_open(self) -> None:
        d = self._make()
        d._open = True
        assert d.height() == 4  # 1 header + 3 options

    def test_dirty(self) -> None:
        d = self._make("a")
        assert not d.dirty
        d.handle_key(curses.KEY_RIGHT)
        assert d.dirty

    def test_render_closed_does_not_raise(self, win: MockWin) -> None:
        d = self._make("a")
        d.render(win, 0, 0, 80, focused=False)  # type: ignore[arg-type]

    def test_render_open_does_not_raise(self, win: MockWin) -> None:
        d = self._make("a")
        d._open = True
        d.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── Button ────────────────────────────────────────────────────────────────────


class TestButton:
    def test_action_called_on_enter(self) -> None:
        called = []

        def action() -> tuple[bool, str]:
            called.append(1)
            return True, "ok"

        btn = Button("Testar", action)
        btn.handle_key(10)
        assert called == [1]

    def test_result_stored(self) -> None:
        btn = Button("Testar", lambda: (True, "Conectado"))
        btn.handle_key(ord(" "))
        assert btn._result == (True, "Conectado")

    def test_result_failure(self) -> None:
        btn = Button("Testar", lambda: (False, "Timeout"))
        btn.handle_key(10)
        assert btn._result is not None
        ok, msg = btn._result
        assert not ok

    def test_clear_result(self) -> None:
        btn = Button("Testar", lambda: (True, "ok"))
        btn.handle_key(10)
        btn.clear_result()
        assert btn._result is None

    def test_height_is_one(self) -> None:
        btn = Button("Testar", lambda: (True, "ok"))
        assert btn.height() == 1

    def test_not_dirty(self) -> None:
        btn = Button("Testar", lambda: (True, "ok"))
        assert not btn.dirty

    def test_render_does_not_raise(self, win: MockWin) -> None:
        btn = Button("Testar", lambda: (True, "ok"))
        btn.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── SectionHeader ─────────────────────────────────────────────────────────────


class TestSectionHeader:
    def test_not_dirty(self) -> None:
        sh = SectionHeader("Título")
        assert not sh.dirty

    def test_key_not_consumed(self) -> None:
        sh = SectionHeader("Título")
        assert not sh.handle_key(ord("x"))

    def test_height_is_one(self) -> None:
        sh = SectionHeader("Título")
        assert sh.height() == 1

    def test_render_does_not_raise(self, win: MockWin) -> None:
        sh = SectionHeader("Título")
        sh.render(win, 0, 0, 80, focused=False)  # type: ignore[arg-type]


# ── CollapsibleSection ────────────────────────────────────────────────────────


class TestCollapsibleSection:
    def _make(self) -> CollapsibleSection:
        children = [
            TextField("A", "Campo A", default="x"),
            TextField("B", "Campo B", default="y"),
        ]
        return CollapsibleSection("Seção", children)

    def test_collapsed_by_default(self) -> None:
        cs = self._make()
        assert not cs.expanded

    def test_enter_expands(self) -> None:
        cs = self._make()
        cs.handle_key(10)
        assert cs.expanded

    def test_enter_collapses(self) -> None:
        cs = self._make()
        cs.handle_key(10)
        cs.handle_key(10)
        assert not cs.expanded

    def test_height_collapsed(self) -> None:
        cs = self._make()
        assert cs.height() == 1

    def test_height_expanded(self) -> None:
        cs = self._make()
        cs.handle_key(10)
        assert cs.height() == 3  # 1 header + 2 children

    def test_dirty_propagates_from_children(self) -> None:
        cs = self._make()
        assert not cs.dirty
        cs.children[0].handle_key(ord("z"))
        assert cs.dirty

    def test_render_collapsed_does_not_raise(self, win: MockWin) -> None:
        cs = self._make()
        cs.render(win, 0, 0, 80, focused=False)  # type: ignore[arg-type]

    def test_render_expanded_does_not_raise(self, win: MockWin) -> None:
        cs = self._make()
        cs.handle_key(10)
        cs.render(win, 0, 0, 80, focused=True)  # type: ignore[arg-type]


# ── HelpPanel ─────────────────────────────────────────────────────────────────


class TestHelpPanel:
    def test_wrap_short_line(self) -> None:
        lines = HelpPanel._wrap("hello world", width=20)
        assert lines == ["hello world"]

    def test_wrap_long_line(self) -> None:
        lines = HelpPanel._wrap("a" * 10 + " " + "b" * 10, width=12)
        assert len(lines) == 2

    def test_wrap_preserves_paragraphs(self) -> None:
        lines = HelpPanel._wrap("line one\n\nline two", width=30)
        assert "" in lines  # parágrafo vazio preservado

    def test_set_and_render_does_not_raise(self, win: MockWin) -> None:
        hp = HelpPanel()
        hp.set("Título", "Texto de ajuda longo que deve ser quebrado automaticamente.")
        hp.render(win, 0, 0, 20)  # type: ignore[arg-type]

    def test_width_constant(self) -> None:
        assert HelpPanel().width == 28


# ── FormPage ──────────────────────────────────────────────────────────────────


class TestFormPage:
    def _make(self) -> tuple[FormPage, list[TextField]]:
        fields = [
            TextField("A", "Alpha", default=""),
            TextField("B", "Beta", default=""),
            TextField("C", "Gamma", default=""),
        ]
        return FormPage(fields), fields

    def test_initial_focus_on_first(self) -> None:
        page, fields = self._make()
        assert page.focused_widget is fields[0]

    def test_tab_advances_focus(self) -> None:
        page, fields = self._make()
        page.handle_key(9)  # Tab
        assert page.focused_widget is fields[1]

    def test_shift_tab_retreats(self) -> None:
        page, fields = self._make()
        page.handle_key(9)
        page.handle_key(curses.KEY_BTAB)
        assert page.focused_widget is fields[0]

    def test_tab_wraps_around(self) -> None:
        page, fields = self._make()
        for _ in range(3):
            page.handle_key(9)
        assert page.focused_widget is fields[0]

    def test_sectionheader_skipped_in_focus(self) -> None:
        from upapasta.tui_widgets import SectionHeader

        sh = SectionHeader("Sep")
        tf = TextField("X", "X", default="")
        page = FormPage([sh, tf])
        assert page.focused_widget is tf

    def test_collect_values_only_dirty(self) -> None:
        page, fields = self._make()
        fields[1].handle_key(ord("z"))
        result = page.collect_values()
        assert "A" not in result
        assert result["B"] == "z"
        assert "C" not in result

    def test_collect_values_empty_when_no_changes(self) -> None:
        page, _ = self._make()
        assert page.collect_values() == {}

    def test_validate_all_passes_empty(self) -> None:
        page, _ = self._make()
        assert page.validate_all() == []

    def test_validate_all_catches_error(self) -> None:
        tf = TextField("K", "L", validator=lambda v: "erro" if not v else None)
        page = FormPage([tf])
        errors = page.validate_all()
        assert len(errors) == 1
        assert "erro" in errors[0]

    def test_load_values_sets_original(self) -> None:
        page, fields = self._make()
        page.load_values({"A": "carregado"})
        assert fields[0].value == "carregado"
        assert not fields[0].dirty  # não marca dirty ao carregar

    def test_load_values_ignores_unknown_keys(self) -> None:
        page, _ = self._make()
        page.load_values({"INEXISTENTE": "x"})  # não deve lançar

    def test_total_height(self) -> None:
        page, fields = self._make()
        assert page.total_height() == 3

    def test_render_does_not_raise(self, win: MockWin) -> None:
        page, _ = self._make()
        page.render(win, 0, 0, 80, 20)  # type: ignore[arg-type]

    def test_collect_values_from_collapsible(self) -> None:
        from upapasta.tui_widgets import CollapsibleSection

        child = TextField("X", "X", default="orig")
        cs = CollapsibleSection("Seção", [child])
        page = FormPage([cs])
        child.handle_key(ord("z"))
        result = page.collect_values()
        assert result["X"] == "origz"

    def test_key_dispatched_to_focused_widget(self) -> None:
        page, fields = self._make()
        page.handle_key(ord("a"))
        assert fields[0].value == "a"
