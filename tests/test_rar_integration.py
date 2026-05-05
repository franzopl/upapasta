"""
Testes de integração para a flag --rar.

Executa o pipeline real com --dry-run para validar se os arquivos RAR
são realmente gerados nas combinações esperadas.
"""

import tempfile
from pathlib import Path

import pytest

from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession
from upapasta.ui import setup_logging


class TestRarIntegrationFile:
    """Testes de integração para arquivo único."""

    @pytest.fixture
    def temp_file(self):
        """Arquivo temporário de 1KB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "movie.mkv"
            f.write_bytes(b"x" * 1024)
            yield f

    def test_rar_only_file_creates_rar(self, temp_file):
        """--rar em arquivo único sem proteção: DEVE gerar RAR (flag explícita honrada)."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_file),
            skip_rar=False,  # --rar
            obfuscate=False,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # --rar explícito deve criar RAR mesmo sem obfuscate/password
        assert orch.rar_file is not None
        assert orch.rar_file.endswith(".rar")

    def test_rar_password_file_generates_rar(self, temp_file):
        """--rar --password em arquivo único: DEVE gerar RAR com senha."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_file),
            skip_rar=False,  # --rar
            obfuscate=False,
            rar_password="mysecret123",
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Arquivo com senha: deve ter criado RAR
        assert orch.rar_file is not None
        assert "movie.rar" in orch.rar_file

    def test_rar_obfuscate_file_generates_rar(self, temp_file):
        """--rar --obfuscate em arquivo único: DEVE gerar RAR."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_file),
            skip_rar=False,  # --rar ativado explicitamente
            obfuscate=True,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # --rar --obfuscate: deve ter criado RAR
        assert orch.rar_file is not None
        assert "movie.rar" in orch.rar_file

    def test_obfuscate_without_rar_file_no_rar(self, temp_file):
        """Apenas --obfuscate em arquivo único (sem --rar): NÃO deve gerar RAR (fluxo moderno)."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_file),
            skip_rar=True,  # Sem --rar (padrão moderno)
            obfuscate=True,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Arquivo com ofuscação mas SEM --rar: não cria RAR (fluxo moderno)
        assert orch.rar_file is None

    def test_rar_password_obfuscate_file_generates_rar(self, temp_file):
        """--rar --password --obfuscate em arquivo único: DEVE gerar RAR com senha, depois ofuscar."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_file),
            skip_rar=False,  # --rar
            obfuscate=True,
            rar_password="mysecret123",
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Ambos: deve ter RAR com senha
        assert orch.rar_file is not None
        assert orch.rar_password == "mysecret123"
        assert "movie.rar" in orch.rar_file


class TestRarIntegrationFolder:
    """Testes de integração para pasta."""

    @pytest.fixture
    def temp_folder(self):
        """Pasta com conteúdo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir) / "MySeries"
            folder.mkdir()
            (folder / "ep01.mkv").write_bytes(b"x" * 1024)
            (folder / "ep02.mkv").write_bytes(b"x" * 1024)
            subfolder = folder / "extras"
            subfolder.mkdir()
            (subfolder / "commentary.mkv").write_bytes(b"x" * 512)
            yield folder

    def test_rar_only_folder_generates_rar(self, temp_folder):
        """--rar em pasta: DEVE gerar RAR."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=False,  # --rar
            obfuscate=False,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Pasta sempre gera RAR quando skip_rar=False
        assert orch.rar_file is not None
        assert "MySeries.rar" in orch.rar_file

    def test_rar_password_folder_generates_rar_with_password(self, temp_folder):
        """--rar --password em pasta: DEVE gerar RAR com senha."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=False,  # --rar
            obfuscate=False,
            rar_password="mysecret123",
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Pasta + senha: gera RAR com senha
        assert orch.rar_file is not None
        assert orch.rar_password == "mysecret123"
        assert "MySeries.rar" in orch.rar_file

    def test_rar_obfuscate_folder_generates_rar_then_obfuscates(self, temp_folder):
        """--rar --obfuscate em pasta: DEVE gerar RAR, depois ofuscar."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=False,  # --rar
            obfuscate=True,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Pasta + ofuscação: gera RAR
        assert orch.rar_file is not None
        assert "MySeries.rar" in orch.rar_file

    def test_rar_password_obfuscate_folder_generates_rar_with_password(self, temp_folder):
        """--rar --password --obfuscate em pasta: DEVE gerar RAR com senha."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=False,  # --rar
            obfuscate=True,
            rar_password="mysecret123",
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Pasta + ambos: gera RAR com senha
        assert orch.rar_file is not None
        assert orch.rar_password == "mysecret123"
        assert "MySeries.rar" in orch.rar_file


class TestNoRarIntegration:
    """Testes de integração para verificar que SEM --rar não gera RAR."""

    @pytest.fixture
    def temp_folder(self):
        """Pasta com conteúdo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir) / "MySeries"
            folder.mkdir()
            (folder / "ep01.mkv").write_bytes(b"x" * 1024)
            yield folder

    def test_no_rar_flag_folder_skips_rar(self, temp_folder):
        """Sem --rar em pasta: DEVE pular RAR (padrão moderno)."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=True,  # Sem --rar (padrão)
            obfuscate=False,
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Sem --rar: não gera RAR
        assert orch.rar_file is None

    def test_no_rar_obfuscate_folder_skips_rar(self, temp_folder):
        """Sem --rar mas com --obfuscate: DEVE pular RAR (fluxo moderno)."""
        setup_logging()
        orch = UpaPastaOrchestrator(
            input_path=str(temp_folder),
            skip_rar=True,  # Sem --rar
            obfuscate=True,  # Mas com --obfuscate
            rar_password=None,
            dry_run=True,
            skip_upload=True,
        )
        with UpaPastaSession(orch) as session:
            try:
                session.run()
            except Exception:
                pass

        # Fluxo moderno: sem RAR, apenas ofuscação
        assert orch.rar_file is None
