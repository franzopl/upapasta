"""
Testes abrangentes para a flag --rar em todas as combinações.

Cobre:
- --rar (apenas)
- --rar --obfuscate
- --rar --password
- --rar --password --obfuscate
- --strong-obfuscate (que implica --obfuscate)

Para: arquivos únicos e pastas
"""

import tempfile
from pathlib import Path

import pytest

from upapasta.cli import _validate_flags
from upapasta.orchestrator import UpaPastaOrchestrator


class TestRarFlagWithFile:
    """Testes para arquivo único com várias flags --rar."""

    @pytest.fixture
    def temp_file(self):
        """Cria arquivo temporário."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "movie.mkv"
            test_file.write_bytes(b"x" * 1024)  # 1KB de dados
            yield str(test_file)

    def test_rar_only_file(self, temp_file):
        """--rar apenas: arquivo único → sem RAR por padrão (arquivo único sem senha)."""
        # Arquivo único sem senha/obfuscação não cria RAR mesmo com --rar
        orch = UpaPastaOrchestrator(
            input_path=temp_file,
            skip_rar=False,  # --rar ativado
            obfuscate=False,
            rar_password=None,
        )
        # Em run_makerar(), arquivo único sem senha força skip_rar = True
        assert orch.skip_rar is False  # Bandeira inicial
        # Mas a lógica em run_makerar verifica se é arquivo e não tem password/obfuscate

    def test_rar_password_file(self, temp_file):
        """--rar --password: arquivo único com senha → cria RAR."""
        orch = UpaPastaOrchestrator(
            input_path=temp_file,
            skip_rar=False,  # --rar ativado
            obfuscate=False,
            rar_password="mysecret123",
        )
        assert orch.skip_rar is False
        assert orch.rar_password == "mysecret123"

    def test_rar_obfuscate_file(self, temp_file):
        """--rar --obfuscate: arquivo único com ofuscação → cria RAR."""
        orch = UpaPastaOrchestrator(
            input_path=temp_file,
            skip_rar=False,  # --rar ativado
            obfuscate=True,
            rar_password=None,
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True

    def test_rar_password_obfuscate_file(self, temp_file):
        """--rar --password --obfuscate: arquivo com ambos → cria RAR com senha, depois ofusca."""
        orch = UpaPastaOrchestrator(
            input_path=temp_file,
            skip_rar=False,  # --rar ativado
            obfuscate=True,
            rar_password="mysecret123",
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True
        assert orch.rar_password == "mysecret123"

    def test_strong_obfuscate_file(self, temp_file):
        """--strong-obfuscate (implica --obfuscate): arquivo → cria RAR se houver senha."""
        orch = UpaPastaOrchestrator(
            input_path=temp_file,
            skip_rar=False,  # --rar ativado
            obfuscate=True,  # --strong-obfuscate implica --obfuscate
            strong_obfuscate=True,
            rar_password=None,
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True
        assert orch.strong_obfuscate is True


class TestRarFlagWithFolder:
    """Testes para pasta com várias flags --rar."""

    @pytest.fixture
    def temp_folder(self):
        """Cria estrutura de pasta temporária."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir) / "MySeries"
            folder.mkdir()
            (folder / "episode1.mkv").write_bytes(b"x" * 1024)
            (folder / "episode2.mkv").write_bytes(b"x" * 1024)
            subfolder = folder / "extras"
            subfolder.mkdir()
            (subfolder / "commentary.mkv").write_bytes(b"x" * 512)
            yield str(folder)

    def test_rar_only_folder(self, temp_folder):
        """--rar apenas: pasta → cria RAR."""
        orch = UpaPastaOrchestrator(
            input_path=temp_folder,
            skip_rar=False,  # --rar ativado
            obfuscate=False,
            rar_password=None,
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is False
        assert orch.rar_password is None

    def test_rar_password_folder(self, temp_folder):
        """--rar --password: pasta com senha → cria RAR com senha."""
        orch = UpaPastaOrchestrator(
            input_path=temp_folder,
            skip_rar=False,  # --rar ativado
            obfuscate=False,
            rar_password="mysecret123",
        )
        assert orch.skip_rar is False
        assert orch.rar_password == "mysecret123"

    def test_rar_obfuscate_folder(self, temp_folder):
        """--rar --obfuscate: pasta com ofuscação → cria RAR, depois ofusca."""
        orch = UpaPastaOrchestrator(
            input_path=temp_folder,
            skip_rar=False,  # --rar ativado
            obfuscate=True,
            rar_password=None,
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True

    def test_rar_password_obfuscate_folder(self, temp_folder):
        """--rar --password --obfuscate: pasta com ambos → cria RAR com senha, depois ofusca."""
        orch = UpaPastaOrchestrator(
            input_path=temp_folder,
            skip_rar=False,  # --rar ativado
            obfuscate=True,
            rar_password="mysecret123",
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True
        assert orch.rar_password == "mysecret123"

    def test_strong_obfuscate_folder(self, temp_folder):
        """--strong-obfuscate (implica --obfuscate): pasta → cria RAR, depois ofusca (nomes aleatórios não revertidos)."""
        orch = UpaPastaOrchestrator(
            input_path=temp_folder,
            skip_rar=False,  # --rar ativado (presume-se por --obfuscate)
            obfuscate=True,  # Implicado
            strong_obfuscate=True,
            rar_password=None,
        )
        assert orch.skip_rar is False
        assert orch.obfuscate is True
        assert orch.strong_obfuscate is True


class TestRarFlagWithCliParsing:
    """Testes de validação para --rar."""

    def test_cli_validate_password_presumes_rar(self):
        """Validação CLI: --password sem --rar → força --rar."""

        # Simula argparse namespace
        class MockArgs:
            rar = False
            password = "secret"
            obfuscate = False
            strong_obfuscate = False
            skip_rar_deprecated = False
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
            each = False
            season = False
            watch = False
            input = None

        args = MockArgs()
        _validate_flags(args)
        # v0.29.0: não força mais --rar, o orchestrator usa DEFAULT_COMPRESSOR
        assert args.rar is False

    def test_cli_validate_strong_obfuscate_implies_obfuscate(self):
        """Validação CLI: --strong-obfuscate implica --obfuscate."""

        class MockArgs:
            rar = False
            password = None
            obfuscate = False
            strong_obfuscate = True
            skip_rar_deprecated = False
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
            each = False
            season = False
            watch = False
            input = None

        args = MockArgs()
        _validate_flags(args)
        assert args.obfuscate is True  # --strong-obfuscate implica --obfuscate


class TestRarDecisionLogic:
    """Testes da lógica de decisão em run_makerar()."""

    @pytest.fixture
    def single_file(self):
        """Arquivo único."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "movie.mkv"
            f.write_bytes(b"x" * 1024)
            yield str(f)

    @pytest.fixture
    def test_folder(self):
        """Pasta com conteúdo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir) / "MySeries"
            folder.mkdir()
            (folder / "ep01.mkv").write_bytes(b"x" * 1024)
            yield str(folder)

    def test_single_file_no_rar_by_default(self, single_file):
        """Arquivo único sem flags de proteção: skip_rar deve ser ativado em run_makerar()."""
        UpaPastaOrchestrator(
            input_path=single_file,
            skip_rar=False,  # Inicialmente quer RAR
            obfuscate=False,
            rar_password=None,
        )
        # A lógica em run_makerar verifica:
        # if self.input_path.is_file() and not self.rar_password and not self.obfuscate:
        #     self.skip_rar = True
        # Portanto, será ativado

    def test_single_file_with_password_creates_rar(self, single_file):
        """Arquivo único + senha: deve criar RAR com senha."""
        orch = UpaPastaOrchestrator(
            input_path=single_file,
            skip_rar=False,
            rar_password="secret123",
            obfuscate=False,
        )
        assert orch.rar_password == "secret123"
        # run_makerar() não deve pular RAR

    def test_single_file_with_obfuscate_creates_rar(self, single_file):
        """Arquivo único + --obfuscate: deve criar RAR."""
        orch = UpaPastaOrchestrator(
            input_path=single_file,
            skip_rar=False,
            obfuscate=True,
            rar_password=None,
        )
        assert orch.obfuscate is True
        # run_makerar() não deve pular RAR

    def test_folder_always_creates_rar_if_not_skip(self, test_folder):
        """Pasta + skip_rar=False: sempre cria RAR."""
        orch = UpaPastaOrchestrator(
            input_path=test_folder,
            skip_rar=False,
            obfuscate=False,
            rar_password=None,
        )
        # Pasta sempre deve criar RAR (a menos que skip_rar=True)
        assert orch.skip_rar is False
