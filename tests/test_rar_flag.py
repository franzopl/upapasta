"""Testes para o comportamento da flag --rar e --skip-rar."""

from __future__ import annotations

import argparse

from upapasta.cli import _validate_flags
from upapasta.orchestrator import UpaPastaOrchestrator


class TestRarFlagLogic:
    def test_rar_flag_true(self):
        """--rar ativa compressão."""
        orch = UpaPastaOrchestrator(input_path="test", skip_rar=False)
        assert orch.skip_rar is False

    def test_rar_flag_false(self):
        """Sem --rar, compressão é pulada."""
        orch = UpaPastaOrchestrator(input_path="test", skip_rar=True)
        assert orch.skip_rar is True

    def test_from_args_rar_flag_inverted(self):
        """from_args deve converter args.rar para skip_rar."""
        args = argparse.Namespace(
            rar=True,
            password=None,
            obfuscate=False,
            dry_run=False,
            redundancy=10,
            backend="parpar",
            post_size=None,
            subject=None,
            group=None,
            skip_par=False,
            skip_upload=False,
            force=False,
            env_file=None,
            keep_files=False,
            rar_threads=None,
            par_threads=None,
            par_profile="balanced",
            nzb_conflict=None,
            par_slice_size=None,
            upload_timeout=None,
            upload_retries=0,
            verbose=False,
            max_memory=None,
            filepath_format="common",
            parpar_args=None,
            nyuu_args=None,
            rename_extensionless=False,
            skip_rar_deprecated=False,
            each=False,
            season=False,
            watch=False,
            compressor=None,
            resume=False,
        )
        # Mock env_vars para evitar carregar arquivo real
        env_vars = {"DEFAULT_COMPRESSOR": "rar"}
        orch = UpaPastaOrchestrator.from_args(args, "test", env_vars=env_vars)
        # Se rar=True, skip_rar deve ser False
        assert orch.skip_rar is False

    def test_from_args_rar_flag_not_set(self):
        """from_args deve converter args.rar=False para skip_rar=True."""
        args = argparse.Namespace(
            rar=False,
            password=None,
            obfuscate=False,
            dry_run=False,
            redundancy=10,
            backend="parpar",
            post_size=None,
            subject=None,
            group=None,
            skip_par=False,
            skip_upload=False,
            force=False,
            env_file=None,
            keep_files=False,
            rar_threads=None,
            par_threads=None,
            par_profile="balanced",
            nzb_conflict=None,
            par_slice_size=None,
            upload_timeout=None,
            upload_retries=0,
            verbose=False,
            max_memory=None,
            filepath_format="common",
            parpar_args=None,
            nyuu_args=None,
            rename_extensionless=False,
            skip_rar_deprecated=False,
            each=False,
            season=False,
            watch=False,
            compressor=None,
            resume=False,
        )
        env_vars = {"DEFAULT_COMPRESSOR": "rar"}
        orch = UpaPastaOrchestrator.from_args(args, "test", env_vars=env_vars)
        # Sem --rar, skip_rar deve ser True (padrão moderno)
        assert orch.skip_rar is True


def test_password_presumes_rar():
    """--password não presume mais --rar automaticamente desde v0.29.0 (usa DEFAULT_COMPRESSOR)."""

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
        skip_rar_deprecated = False
        obfuscate = False
        strong_obfuscate = False
        each = False
        season = False
        watch = False
        compressor = None
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

    args = MockArgs()
    _validate_flags(args)
    # v0.29.0: não força mais --rar, o orchestrator usa DEFAULT_COMPRESSOR
    assert args.rar is False


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
        skip_rar_deprecated = False
        strong_obfuscate = False
        each = False
        season = False
        watch = False
        compressor = None
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

    args = MockArgs()
    _validate_flags(args)
    assert args.rar is False
