"""
Testes para a nova flag --rar (positiva).
"""

import tempfile
from pathlib import Path

from upapasta.orchestrator import UpaPastaOrchestrator


def test_rar_flag_false_skip_rar_true():
    """--rar não está ativado (padrão) → skip_rar deve ser True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        orch = UpaPastaOrchestrator(
            input_path=str(test_file),
            skip_rar=True,  # Equivalente a: --rar não ativado
        )
        assert orch.skip_rar is True


def test_rar_flag_true_skip_rar_false():
    """--rar ativado → skip_rar deve ser False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        orch = UpaPastaOrchestrator(
            input_path=str(test_file),
            skip_rar=False,  # Equivalente a: --rar ativado
        )
        assert orch.skip_rar is False


def test_from_args_rar_flag_inverted():
    """from_args deve inverter a flag: --rar → skip_rar=False."""

    class MockArgs:
        rar = True
        dry_run = False
        redundancy = None
        backend = "parpar"
        post_size = None
        subject = None
        group = None
        skip_par = False
        skip_upload = False
        force = False
        env_file = ".env"
        keep_files = False
        rar_threads = None
        par_threads = None
        par_profile = "balanced"
        nzb_conflict = None
        obfuscate = False
        password = None
        par_slice_size = None
        upload_timeout = None
        upload_retries = 0
        verbose = False
        max_memory = None
        filepath_format = "common"
        parpar_args = None
        nyuu_args = None
        rename_extensionless = False

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        args = MockArgs()
        orch = UpaPastaOrchestrator.from_args(args, str(test_file))

        # Com --rar (True), skip_rar deve ser False
        assert orch.skip_rar is False


def test_from_args_rar_flag_not_set():
    """from_args sem --rar → skip_rar=True (padrão moderno)."""

    class MockArgs:
        rar = False  # Sem --rar
        dry_run = False
        redundancy = None
        backend = "parpar"
        post_size = None
        subject = None
        group = None
        skip_par = False
        skip_upload = False
        force = False
        env_file = ".env"
        keep_files = False
        rar_threads = None
        par_threads = None
        par_profile = "balanced"
        nzb_conflict = None
        obfuscate = False
        password = None
        par_slice_size = None
        upload_timeout = None
        upload_retries = 0
        verbose = False
        max_memory = None
        filepath_format = "common"
        parpar_args = None
        nyuu_args = None
        rename_extensionless = False

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        args = MockArgs()
        orch = UpaPastaOrchestrator.from_args(args, str(test_file))

        # Sem --rar, skip_rar deve ser True (padrão moderno)
        assert orch.skip_rar is True
