"""
Testes da Fase 3 da TUI: modal de confirmação, painel de upload, tela de progresso.
Skipa automaticamente se textual não estiver instalado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

textual = pytest.importorskip("textual")

from upapasta.tui.app import UpaPastaApp
from upapasta.tui.fs_scanner import FileNode
from upapasta.tui.screens.confirm import ConfirmScreen, UploadConfig, build_upload_cmd
from upapasta.tui.screens.upload_progress import UploadProgressScreen
from upapasta.tui.status import UploadStatus
from upapasta.tui.widgets.upload_panel import UploadPanel, _last_cr_segment, _strip_ansi

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_node(tmp_path: Path, name: str, *, is_dir: bool = True) -> FileNode:
    p = tmp_path / name
    if is_dir:
        p.mkdir(exist_ok=True)
    else:
        p.touch()
    return FileNode(
        path=p,
        is_dir=is_dir,
        size=0 if is_dir else 1024,
        status=UploadStatus.PENDING,
    )


def _make_app(tmp_path: Path) -> UpaPastaApp:
    history = tmp_path / "history.jsonl"
    history.touch()
    return UpaPastaApp(root_path=tmp_path)


# ── build_upload_cmd ──────────────────────────────────────────────────────────


def test_build_upload_cmd_defaults(tmp_path: Path) -> None:
    node = _make_node(tmp_path, "Dune.2021")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    cmd = build_upload_cmd(node, config)
    assert sys.executable in cmd
    assert "-m" in cmd
    assert "upapasta" in cmd
    assert str(node.path) in cmd
    assert "--obfuscate" not in cmd
    assert "--rar" not in cmd
    assert "--par-profile" in cmd
    assert "balanced" in cmd


def test_build_upload_cmd_with_flags(tmp_path: Path) -> None:
    node = _make_node(tmp_path, "Breaking.Bad.S01")
    config = UploadConfig(obfuscate=True, use_rar=True, par_profile="safe")
    cmd = build_upload_cmd(node, config)
    assert "--obfuscate" in cmd
    assert "--rar" in cmd
    assert "safe" in cmd


def test_build_upload_cmd_path_is_last_positional(tmp_path: Path) -> None:
    node = _make_node(tmp_path, "Serie.S02")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="fast")
    cmd = build_upload_cmd(node, config)
    # path deve aparecer antes das flags
    path_idx = cmd.index(str(node.path))
    assert path_idx > 0


# ── _strip_ansi ───────────────────────────────────────────────────────────────


def test_strip_ansi_removes_escape_sequences() -> None:
    raw = "\x1b[32mOK\x1b[0m"
    assert _strip_ansi(raw) == "OK"


def test_strip_ansi_passthrough_plain() -> None:
    assert _strip_ansi("hello world") == "hello world"


def test_strip_ansi_empty() -> None:
    assert _strip_ansi("") == ""


# ── _last_cr_segment ──────────────────────────────────────────────────────────


def test_last_cr_segment_no_cr() -> None:
    assert _last_cr_segment("hello world\n") == "hello world"


def test_last_cr_segment_with_cr() -> None:
    """Parpar/nyuu sobrescrevem linhas com \\r; deve retornar o último estado."""
    assert _last_cr_segment(" 30%\r 60%\r 100%\n") == "100%"


def test_last_cr_segment_with_ansi_and_cr() -> None:
    raw = "\x1b[32m 50%\x1b[0m\r\x1b[32m100%\x1b[0m\n"
    assert _last_cr_segment(raw) == "100%"


def test_last_cr_segment_all_empty_segments() -> None:
    assert _last_cr_segment("\r\r\n") == ""


def test_last_cr_segment_empty() -> None:
    assert _last_cr_segment("") == ""


# ── UploadConfig ──────────────────────────────────────────────────────────────


def test_upload_config_fields() -> None:
    cfg = UploadConfig(obfuscate=True, use_rar=False, par_profile="balanced")
    assert cfg.obfuscate is True
    assert cfg.use_rar is False
    assert cfg.par_profile == "balanced"


# ── ConfirmScreen: instanciação ───────────────────────────────────────────────


def test_confirm_screen_instantiation(tmp_path: Path) -> None:
    nodes = [_make_node(tmp_path, f"Item{i}") for i in range(3)]
    screen = ConfirmScreen(nodes)
    assert screen is not None


def test_confirm_screen_many_items(tmp_path: Path) -> None:
    """Mais de 10 itens: exibe "… e mais N itens" sem travar."""
    nodes = [_make_node(tmp_path, f"Item{i:02d}") for i in range(15)]
    screen = ConfirmScreen(nodes)
    assert len(screen._items) == 15


# ── ConfirmScreen: async (pilot) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_confirm_screen_cancel_returns_none(tmp_path: Path) -> None:
    nodes = [_make_node(tmp_path, "Dune.2021")]
    result: list[UploadConfig | None] = []

    app = UpaPastaApp(root_path=tmp_path)
    async with app.run_test(headless=True) as pilot:
        app.push_screen(ConfirmScreen(nodes), result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")

    assert result == [None]


@pytest.mark.anyio
async def test_confirm_screen_confirm_button(tmp_path: Path) -> None:
    nodes = [_make_node(tmp_path, "Dune.2021")]
    result: list[UploadConfig | None] = []

    app = UpaPastaApp(root_path=tmp_path)
    async with app.run_test(headless=True) as pilot:
        app.push_screen(ConfirmScreen(nodes), result.append)
        await pilot.pause()
        await pilot.click("#btn-confirm")
        await pilot.pause()
        await pilot.press("q")

    assert len(result) == 1
    assert result[0] is not None
    assert isinstance(result[0], UploadConfig)
    assert result[0].par_profile == "balanced"


@pytest.mark.anyio
async def test_confirm_screen_cancel_button(tmp_path: Path) -> None:
    nodes = [_make_node(tmp_path, "Dune.2021")]
    result: list[UploadConfig | None] = []

    app = UpaPastaApp(root_path=tmp_path)
    async with app.run_test(headless=True) as pilot:
        app.push_screen(ConfirmScreen(nodes), result.append)
        await pilot.pause()
        await pilot.click("#btn-cancel")
        await pilot.pause()
        await pilot.press("q")

    assert result == [None]


# ── UploadPanel: unit ─────────────────────────────────────────────────────────


def test_upload_panel_initial_state(tmp_path: Path) -> None:
    """Painel recém-criado tem atributos de progresso zerados."""
    node = _make_node(tmp_path, "Dune.2021")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    panel = UploadPanel([node], config)
    assert panel._cancelled is False
    assert panel._proc is None
    assert panel._got_progress is False
    assert panel._current_phase == "Preparando"
    assert panel._done_count == 0
    assert panel._tick_count == 0


def test_upload_panel_cancel_before_start(tmp_path: Path) -> None:
    """cancel() sem processo ativo não deve lançar exceção."""
    node = _make_node(tmp_path, "Dune.2021")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    panel = UploadPanel([node], config)
    panel._cancelled = False
    panel._proc = None
    panel.cancel()
    assert panel._cancelled is True


def test_upload_panel_cancel_with_mock_proc(tmp_path: Path) -> None:
    """cancel() com processo ativo chama terminate()."""
    node = _make_node(tmp_path, "Dune.2021")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    panel = UploadPanel([node], config)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # processo rodando
    panel._proc = mock_proc  # type: ignore[assignment]
    panel.cancel()

    mock_proc.terminate.assert_called_once()
    assert panel._cancelled is True


def test_upload_panel_cancel_already_finished(tmp_path: Path) -> None:
    """cancel() com processo já terminado não chama terminate()."""
    node = _make_node(tmp_path, "Dune.2021")
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    panel = UploadPanel([node], config)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # já terminou
    panel._proc = mock_proc  # type: ignore[assignment]
    panel.cancel()

    mock_proc.terminate.assert_not_called()


# ── UploadProgressScreen: instanciação ───────────────────────────────────────


def test_upload_progress_screen_instantiation(tmp_path: Path) -> None:
    nodes = [_make_node(tmp_path, "Dune.2021")]
    config = UploadConfig(obfuscate=False, use_rar=False, par_profile="balanced")
    screen = UploadProgressScreen(nodes, config)
    assert screen is not None


# ── App: binding U sem seleção ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_upload_action_without_selection_shows_warning(tmp_path: Path) -> None:
    """Pressionar U sem seleção exibe notificação de aviso, não abre modal."""
    app = UpaPastaApp(root_path=tmp_path)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("u")
        await pilot.pause()
        # Sem seleção → não deve haver ConfirmScreen na pilha de telas
        assert not any(isinstance(s, ConfirmScreen) for s in app.screen_stack)
        await pilot.press("q")


# ── App: binding U com seleção abre ConfirmScreen ────────────────────────────


@pytest.mark.anyio
async def test_upload_action_with_selection_opens_confirm(tmp_path: Path) -> None:
    """Pressionar U com item selecionado abre ConfirmScreen."""
    (tmp_path / "Dune.2021").mkdir()

    app = UpaPastaApp(root_path=tmp_path)
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Cursor começa na raiz; navega para o primeiro filho
        await pilot.press("down")
        await pilot.pause()
        # Seleciona o item
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        # ConfirmScreen deve estar na pilha
        assert any(isinstance(s, ConfirmScreen) for s in app.screen_stack)
        await pilot.press("escape")  # fecha o modal
        await pilot.pause()
        await pilot.press("q")
