"""
hooks.py

Sistema de plugins nativos em Python.
Executa scripts em ~/.config/upapasta/hooks/ após o upload.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
from typing import Any

from .config import CONFIG_DIR
from .i18n import _


def run_python_hooks(metadata: dict[str, Any]) -> None:
    """Carrega e executa todos os hooks Python na pasta ~/.config/upapasta/hooks/."""
    hooks_dir = os.path.join(CONFIG_DIR, "hooks")
    if not os.path.exists(hooks_dir):
        return

    try:
        hook_files = [
            f for f in os.listdir(hooks_dir) if f.endswith(".py") and not f.startswith("_")
        ]
    except OSError:
        return

    if not hook_files:
        return

    for filename in sorted(hook_files):
        hook_path = os.path.join(hooks_dir, filename)
        module_name = f"upapasta.hooks.user.{filename[:-3]}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, hook_path)
            if not spec or not spec.loader:
                continue

            module = importlib.util.module_from_spec(spec)
            # Adiciona ao sys.modules para evitar problemas de importação relativa se houver
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "on_upload_complete"):
                # Executa a função do plugin
                func = getattr(module, "on_upload_complete")
                func(metadata)
        except Exception as e:
            print(_("⚠️  Erro ao executar hook '{hook}': {error}").format(hook=filename, error=e))
            # No modo normal mostramos apenas o erro, mas guardamos o traceback para debug se necessário
            traceback.print_exc(file=sys.stdout)
