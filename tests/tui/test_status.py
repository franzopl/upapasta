"""Testes para upapasta.tui.status."""

from __future__ import annotations

import pytest

from upapasta.tui.status import UploadStatus


def test_all_values_have_icon() -> None:
    for status in UploadStatus:
        assert status.icon, f"{status} sem ícone"


def test_all_values_have_color() -> None:
    for status in UploadStatus:
        assert status.color, f"{status} sem cor"


def test_all_values_have_label() -> None:
    for status in UploadStatus:
        assert status.label, f"{status} sem label"


def test_specific_icons() -> None:
    assert UploadStatus.UPLOADED.icon == "✅"
    assert UploadStatus.PENDING.icon == "❌"
    assert UploadStatus.PARTIAL.icon == "🔶"
    assert UploadStatus.IN_PROGRESS.icon == "⏳"


def test_specific_colors() -> None:
    assert UploadStatus.UPLOADED.color == "green"
    assert UploadStatus.PENDING.color == "red"
    assert UploadStatus.PARTIAL.color == "yellow"
    assert UploadStatus.IN_PROGRESS.color == "cyan"


def test_specific_labels() -> None:
    assert UploadStatus.UPLOADED.label == "Enviado"
    assert UploadStatus.PENDING.label == "Pendente"
    assert UploadStatus.PARTIAL.label == "Parcial"


def test_enum_values_are_strings() -> None:
    for status in UploadStatus:
        assert isinstance(status.value, str)


@pytest.mark.parametrize("status", list(UploadStatus))
def test_icon_is_nonempty_string(status: UploadStatus) -> None:
    assert isinstance(status.icon, str)
    assert len(status.icon) > 0


@pytest.mark.parametrize("status", list(UploadStatus))
def test_color_is_nonempty_string(status: UploadStatus) -> None:
    assert isinstance(status.color, str)
    assert len(status.color) > 0
