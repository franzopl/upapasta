"""
Testes para a nova flag --rar (positiva) e comportamento de --password.
"""

import tempfile
from pathlib import Path

from upapasta.cli import _validate_flags
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
        skip_rar_deprecated = False
        each = False
        season = False
        watch = False
        input = None

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
        skip_rar_deprecated = False
        each = False
        season = False
        watch = False
        input = None

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        args = MockArgs()
        orch = UpaPastaOrchestrator.from_args(args, str(test_file))

        # Sem --rar, skip_rar deve ser True (padrão moderno)
        assert orch.skip_rar is True


def test_password_presumes_rar():
    """--password presume --rar automaticamente."""

    class MockArgs:
        rar = False  # Inicialmente sem --rar
        password = "abc123"  # Mas com --password
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
        par_slice_size = None
        upload_timeout = None
        upload_retries = 0
        verbose = False
        max_memory = None
        filepath_format = "common"
        parpar_args = None
        nyuu_args = None
        rename_extensionless = False
        skip_rar_deprecated = False
        each = False
        season = False
        watch = False
        input = None

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        args = MockArgs()

        # Antes da validação
        assert args.rar is False

        # Validar flags
        result = _validate_flags(args)

        # Depois da validação, --rar deve ter sido ativado
        assert result is True
        assert args.rar is True


def test_obfuscate_without_rar():
    """--obfuscate não presume --rar (fluxo moderno)."""

    class MockArgs:
        rar = False
        obfuscate = True
        password = None
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
        par_slice_size = None
        upload_timeout = None
        upload_retries = 0
        verbose = False
        max_memory = None
        filepath_format = "common"
        parpar_args = None
        nyuu_args = None
        rename_extensionless = False
        skip_rar_deprecated = False
        each = False
        season = False
        watch = False
        input = None

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        args = MockArgs()

        # Validar flags
        result = _validate_flags(args)

        # --rar não deve ser ativado por --obfuscate
        assert result is True
        assert args.rar is False
