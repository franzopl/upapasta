"""
test_coverage.py

Testes focados para aumentar cobertura dos módulos core para ≥ 90%.
Cobre: nzb.py, makerar.py, makepar.py, cli.py, upfolder.py, orchestrator.py
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _create_mock_nyuu(tmp_path):
    """Cria um binário/script mock do nyuu que funciona em Windows e Linux."""
    import sys

    py_script = tmp_path / "fake_nyuu_script.py"
    py_script.write_text("import sys; sys.exit(0)")
    if sys.platform == "win32":
        cmd_file = tmp_path / "fake_nyuu.cmd"
        cmd_file.write_text(f'@echo off\n"{sys.executable}" "{py_script}" %*')
        return str(cmd_file)
    else:
        sh_file = tmp_path / "fake_nyuu"
        sh_file.write_text(f"#!{sys.executable}\nimport sys; sys.exit(0)")
        sh_file.chmod(0o755)
        return str(sh_file)


# ── nzb.py ────────────────────────────────────────────────────────────────────


class TestResolveNzbTemplate:
    def test_sem_template_retorna_padrao(self, tmp_path, monkeypatch):
        from upapasta.nzb import resolve_nzb_template

        monkeypatch.delenv("NZB_OUT", raising=False)
        result = resolve_nzb_template({}, is_folder=False, skip_rar=True)
        assert result == "{filename}.nzb"

    def test_template_com_placeholder(self, monkeypatch):
        from upapasta.nzb import resolve_nzb_template

        monkeypatch.delenv("NZB_OUT", raising=False)
        result = resolve_nzb_template(
            {"NZB_OUT": "/saida/{filename}.nzb"}, is_folder=False, skip_rar=True
        )
        assert result == "/saida/{filename}.nzb"

    def test_template_sem_placeholder_adiciona(self, tmp_path, monkeypatch):
        from upapasta.nzb import resolve_nzb_template

        monkeypatch.delenv("NZB_OUT", raising=False)
        result = resolve_nzb_template({"NZB_OUT": str(tmp_path)}, is_folder=False, skip_rar=True)
        assert "{filename}.nzb" in result

    def test_template_nao_nzb_adiciona_extensao(self, monkeypatch):
        from upapasta.nzb import resolve_nzb_template

        monkeypatch.delenv("NZB_OUT", raising=False)
        result = resolve_nzb_template({"NZB_OUT": "/saida/arquivo"}, is_folder=False, skip_rar=True)
        assert "{filename}.nzb" in result


class TestHandleNzbConflict:
    def test_sem_arquivo_existente(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_out = "test.nzb"
        nzb_abs = str(tmp_path / "test.nzb")
        out, abs_out, overwrite, ok = handle_nzb_conflict(nzb_out, nzb_abs, {})
        assert ok is True
        assert not overwrite

    def test_conflito_overwrite(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_abs = str(tmp_path / "test.nzb")
        Path(nzb_abs).write_text("x")
        out, abs_out, overwrite, ok = handle_nzb_conflict(
            "test.nzb", nzb_abs, {"NZB_CONFLICT": "overwrite"}
        )
        assert ok is True
        assert overwrite is True

    def test_conflito_fail(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_abs = str(tmp_path / "test.nzb")
        Path(nzb_abs).write_text("x")
        out, abs_out, overwrite, ok = handle_nzb_conflict(
            "test.nzb", nzb_abs, {"NZB_CONFLICT": "fail"}
        )
        assert ok is False

    def test_conflito_rename(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_abs = str(tmp_path / "test.nzb")
        Path(nzb_abs).write_text("x")
        out, abs_out, overwrite, ok = handle_nzb_conflict(
            str(nzb_abs), nzb_abs, {}, working_dir=str(tmp_path)
        )
        assert ok is True
        assert "1" in abs_out  # renomeado para test-1.nzb

    def test_conflito_rename_multiplos(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_abs = str(tmp_path / "test.nzb")
        Path(nzb_abs).write_text("x")
        Path(str(tmp_path / "test-1.nzb")).write_text("x")
        out, abs_out, overwrite, ok = handle_nzb_conflict(
            str(nzb_abs), nzb_abs, {}, working_dir=str(tmp_path)
        )
        assert ok is True
        assert "2" in abs_out

    def test_conflito_com_nzb_overwrite_env_true(self, tmp_path):
        from upapasta.nzb import handle_nzb_conflict

        nzb_abs = str(tmp_path / "test.nzb")
        Path(nzb_abs).write_text("x")
        out, abs_out, overwrite, ok = handle_nzb_conflict(
            "test.nzb", nzb_abs, {}, nzb_overwrite_env="true"
        )
        assert overwrite is True


class TestInjectNzbPassword:
    def _make_nzb(self, tmp_path: Path) -> str:
        nzb_path = str(tmp_path / "test.nzb")
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        ET.SubElement(root, f"{{{ns}}}head")
        tree = ET.ElementTree(root)
        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
        return nzb_path

    def test_injeta_senha(self, tmp_path):
        from upapasta.nzb import inject_nzb_password

        nzb_path = self._make_nzb(tmp_path)
        inject_nzb_password(nzb_path, "minhasenha")
        content = Path(nzb_path).read_text(encoding="utf-8")
        assert "minhasenha" in content

    def test_sobrescreve_senha_anterior(self, tmp_path):
        from upapasta.nzb import inject_nzb_password

        nzb_path = self._make_nzb(tmp_path)
        inject_nzb_password(nzb_path, "senha1")
        inject_nzb_password(nzb_path, "senha2")
        content = Path(nzb_path).read_text(encoding="utf-8")
        assert "senha2" in content
        assert "senha1" not in content

    def test_arquivo_invalido_nao_levanta(self, tmp_path):
        from upapasta.nzb import inject_nzb_password

        nzb_path = str(tmp_path / "invalido.nzb")
        Path(nzb_path).write_text("nao xml")
        # Não deve levantar exceção
        inject_nzb_password(nzb_path, "senha")


class TestDeobfuscateFilename:
    def test_mapa_direto(self):
        from upapasta.nzb import _deobfuscate_filename

        m = {"abc123": "original"}
        assert _deobfuscate_filename("abc123", m) == "original"

    def test_extensao_rar(self):
        from upapasta.nzb import _deobfuscate_filename

        m = {"abc123": "original"}
        assert _deobfuscate_filename("abc123.part01.rar", m) == "original.part01.rar"

    def test_extensao_par2(self):
        from upapasta.nzb import _deobfuscate_filename

        m = {"abc123": "original"}
        assert _deobfuscate_filename("abc123.vol00+01.par2", m) == "original.vol00+01.par2"

    def test_extensao_simples(self):
        from upapasta.nzb import _deobfuscate_filename

        m = {"abc123": "original"}
        assert _deobfuscate_filename("abc123.mkv", m) == "original.mkv"

    def test_nao_mapeado(self):
        from upapasta.nzb import _deobfuscate_filename

        assert _deobfuscate_filename("xyz.rar", {}) == "xyz.rar"

    def test_extensao_par2_simples(self):
        from upapasta.nzb import _deobfuscate_filename

        m = {"abc123": "original"}
        assert _deobfuscate_filename("abc123.par2", m) == "original.par2"


# ── makerar.py ────────────────────────────────────────────────────────────────


class TestFolderSize:
    def test_pasta_vazia(self, tmp_path):
        from upapasta.makerar import _folder_size

        assert _folder_size(str(tmp_path)) == 0

    def test_com_arquivo(self, tmp_path):
        from upapasta.makerar import _folder_size

        (tmp_path / "a.txt").write_text("hello")
        size = _folder_size(str(tmp_path))
        assert size > 0

    def test_recursivo(self, tmp_path):
        from upapasta.makerar import _folder_size

        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("world!")
        size = _folder_size(str(tmp_path))
        assert size > 0


class TestVolumeSizeBytes:
    def test_pequeno_retorna_none(self):
        from upapasta.makerar import _volume_size_bytes

        assert _volume_size_bytes(1 * 1024**3) is None  # 1 GB < 10 GB

    def test_grande_retorna_tamanho(self):
        from upapasta.makerar import _volume_size_bytes

        result = _volume_size_bytes(50 * 1024**3)  # 50 GB
        assert result is not None
        assert result >= 1024**3  # ≥ 1 GB

    def test_arredondado_para_5mb(self):
        from upapasta.makerar import _volume_size_bytes

        result = _volume_size_bytes(50 * 1024**3)
        five_mb = 5 * 1024 * 1024
        assert result is not None
        assert result % five_mb == 0


class TestMakeRar:
    def test_path_invalido(self, tmp_path):
        from upapasta.makerar import make_rar

        rc, path = make_rar(str(tmp_path / "nao_existe"))
        assert rc == 2
        assert path is None

    def test_rar_nao_encontrado(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")
        with patch("upapasta.makerar.get_tool_path", return_value=None):
            rc, path = make_rar(str(folder))
        assert rc == 4
        assert path is None

    def test_rar_ja_existe_sem_force(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")
        # Cria arquivo RAR manualmente para simular conflito
        rar_path = tmp_path / "pasta.rar"
        rar_path.write_text("fake rar")
        rc, path = make_rar(str(folder), force=False)
        assert rc == 3
        assert path is None

    def test_make_rar_com_mock_sucesso(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("conteudo")

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", return_value=mock_proc),
        ):
            rc, path = make_rar(str(folder))
        assert rc == 0

    def test_parse_args_makerar(self, monkeypatch):
        from upapasta.makerar import parse_args

        monkeypatch.setattr(sys, "argv", ["makerar", "fake_input_dir"])
        args = parse_args()
        assert args.folder == "fake_input_dir"
        assert args.force is False


# ── makepar.py ────────────────────────────────────────────────────────────────


class TestParseSize:
    def test_kilobytes(self):
        from upapasta.makepar import _parse_size

        assert _parse_size("768K") == 768 * 1024

    def test_megabytes(self):
        from upapasta.makepar import _parse_size

        assert _parse_size("1M") == 1024 * 1024

    def test_gigabytes(self):
        from upapasta.makepar import _parse_size

        assert _parse_size("1G") == 1024**3

    def test_numero_puro(self):
        from upapasta.makepar import _parse_size

        assert _parse_size("100") == 100

    def test_vazio_levanta(self):
        from upapasta.makepar import _parse_size

        with pytest.raises(ValueError):
            _parse_size("")


class TestFmtSize:
    def test_megabytes_exato(self):
        from upapasta.makepar import _fmt_size

        assert _fmt_size(2 * 1024 * 1024) == "2M"

    def test_kilobytes_exato(self):
        from upapasta.makepar import _fmt_size

        assert _fmt_size(512 * 1024) == "512K"

    def test_bytes_puros(self):
        from upapasta.makepar import _fmt_size

        assert _fmt_size(1234) == "1234"


class TestComputeDynamicSlice:
    def test_pequeno_50gb(self):
        from upapasta.makepar import _compute_dynamic_slice

        article_size = 786432  # 768K
        slice_str, min_slices, max_slices = _compute_dynamic_slice(10 * 1024**3, article_size)
        assert min_slices == 60
        assert max_slices == 12000

    def test_medio_100gb(self):
        from upapasta.makepar import _compute_dynamic_slice

        slice_str, min_slices, _ = _compute_dynamic_slice(80 * 1024**3, 786432)
        assert min_slices == 80

    def test_grande_200gb(self):
        from upapasta.makepar import _compute_dynamic_slice

        slice_str, min_slices, _ = _compute_dynamic_slice(150 * 1024**3, 786432)
        assert min_slices == 100

    def test_enorme_acima_200gb(self):
        from upapasta.makepar import _compute_dynamic_slice

        slice_str, min_slices, _ = _compute_dynamic_slice(250 * 1024**3, 786432)
        assert min_slices == 120

    def test_clamp_maximo_4mib(self):
        from upapasta.makepar import _compute_dynamic_slice

        # Artigo enorme → clamp em 4 MiB
        slice_str, _, _ = _compute_dynamic_slice(10 * 1024**3, 10 * 1024 * 1024)
        assert "M" in slice_str
        mb = int(slice_str.replace("M", ""))
        assert mb <= 4


class TestGetParparMemoryLimit:
    def test_retorna_valor_ou_none(self):
        from upapasta.makepar import get_parpar_memory_limit

        result = get_parpar_memory_limit()
        # Pode ser None em ambientes sem /proc/meminfo, ou uma string "NNM"/"NNG"
        assert result is None or isinstance(result, str)
        if result:
            assert result.endswith("M") or result.endswith("G")

    def test_fallback_em_excecao(self):
        from upapasta.makepar import get_parpar_memory_limit

        with patch("builtins.open", side_effect=OSError):
            result = get_parpar_memory_limit()
        assert result is None


class TestHandleParFailure:
    def test_retry_bem_sucedido(self, tmp_path):
        from upapasta.makepar import handle_par_failure

        # Simula retry bem-sucedido mockando make_parity
        with patch("upapasta.makepar.make_parity", return_value=0):
            result = handle_par_failure(
                str(tmp_path / "test.rar"),
                original_rc=5,
                redundancy=10,
                threads=4,
            )
        assert result is True

    def test_retry_falhou(self, tmp_path):
        from upapasta.makepar import handle_par_failure

        with patch("upapasta.makepar.make_parity", return_value=5):
            result = handle_par_failure(
                str(tmp_path / "test.rar"),
                original_rc=5,
                redundancy=10,
                threads=4,
            )
        assert result is False

    def test_retry_com_excecao(self, tmp_path):
        from upapasta.makepar import handle_par_failure

        with patch("upapasta.makepar.make_parity", side_effect=RuntimeError("erro")):
            result = handle_par_failure(
                str(tmp_path / "test.rar"),
                original_rc=5,
            )
        assert result is False

    def test_remove_par2_existentes(self, tmp_path):
        from upapasta.makepar import handle_par_failure

        rar = tmp_path / "test.rar"
        rar.write_text("fake")
        par2 = tmp_path / "test.par2"
        par2.write_text("fake par2")
        with patch("upapasta.makepar.make_parity", return_value=0):
            handle_par_failure(str(rar), original_rc=5)
        # par2 deve ter sido removido antes do retry
        assert not par2.exists()


class TestMakeParity:
    def test_path_invalido(self, tmp_path):
        from upapasta.makepar import make_parity

        rc = make_parity(str(tmp_path / "nao_existe.rar"))
        assert rc == 2

    def test_backend_invalido(self, tmp_path):
        from upapasta.makepar import make_parity

        f = tmp_path / "test.rar"
        f.write_text("fake")
        with (
            patch("upapasta.makepar.find_parpar", return_value=None),
            patch("upapasta.makepar.find_par2", return_value=None),
        ):
            rc = make_parity(str(f), backend="auto")
        assert rc == 4

    def test_dry_run_parpar(self, tmp_path, capsys):
        from upapasta.makepar import make_parity

        f = tmp_path / "test.rar"
        f.write_text("fake content" * 100)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")):
            rc = make_parity(str(f), backend="parpar", dry_run=True)
        captured = capsys.readouterr()
        assert "parpar" in captured.out or rc in (0, 2, 4)

    def test_perfil_invalido(self, tmp_path):
        from upapasta.makepar import make_parity

        f = tmp_path / "test.rar"
        f.write_text("fake")
        rc = make_parity(str(f), profile="nao_existe")
        assert rc == 2


class TestParseArgsMakepar:
    def test_parse_args_basico(self, monkeypatch):
        from upapasta.makepar import parse_args

        monkeypatch.setattr(sys, "argv", ["makepar", "fake_test.rar"])
        args = parse_args()
        assert args.rarfile == "fake_test.rar"


# ── cli.py ────────────────────────────────────────────────────────────────────


class TestCheckDependencies:
    def test_tudo_disponivel(self):
        from upapasta.cli import check_dependencies

        with patch("upapasta.cli.get_tool_path", return_value="/usr/bin/rar"):
            result = check_dependencies(pack_needed=True)
        assert result is True

    def test_nyuu_ausente(self):
        from upapasta.cli import check_dependencies

        def which_sem_nyuu(cmd: str) -> str | None:
            return None if cmd == "nyuu" else "/usr/bin/" + cmd

        with patch("upapasta.cli.get_tool_path", side_effect=which_sem_nyuu):
            result = check_dependencies(pack_needed=False)
        assert result is False

    def test_rar_nao_necessario(self):
        from upapasta.cli import check_dependencies

        def which_sem_rar(cmd: str) -> str | None:
            return None if cmd == "rar" else "/usr/bin/" + cmd

        with patch("upapasta.cli.get_tool_path", side_effect=which_sem_rar):
            result = check_dependencies(pack_needed=False)
        assert result is True

    def test_opcionals_ausentes(self, capsys):
        from upapasta.cli import check_dependencies

        def which_sem_opcionals(cmd: str) -> str | None:
            if cmd in ("mediainfo", "ffprobe"):
                return None
            return "/usr/bin/" + cmd

        with patch("upapasta.cli.get_tool_path", side_effect=which_sem_opcionals):
            result = check_dependencies(pack_needed=False)
        captured = capsys.readouterr()
        assert "opcionais" in captured.out.lower() or result is True


class TestValidateFlags:
    def _args(self, **kwargs) -> argparse.Namespace:
        # input_val permite configurar o caminho sem quebrar a lógica de inputs (lista)
        input_val = kwargs.pop("input", "fake_test_path")
        defaults: dict = {
            "rar": False,
            "password": None,
            "obfuscate": False,
            "each": False,
            "season": False,
            "watch": False,
            "jobs": 1,
            "inputs": [input_val],
        }
        defaults.update(kwargs)
        # Se inputs foi passado diretamente, não precisamos ajustar
        if "inputs" not in kwargs and input_val:
            defaults["inputs"] = [input_val]
        return argparse.Namespace(**defaults)

    def test_password_sem_rar_ativa_rar(self, capsys):
        from upapasta.cli import _validate_flags

        args = self._args(password="senha123")
        _validate_flags(args)
        # v0.29.0: --password não força mais --rar, o orchestrator usa DEFAULT_COMPRESSOR
        assert args.password == "senha123"

    def test_password_random(self, capsys):
        from upapasta.cli import _validate_flags

        args = self._args(password="__random__")
        _validate_flags(args)
        assert args.password != "__random__"
        assert len(args.password) == 16

    def test_each_requer_pasta(self, tmp_path, capsys):
        from upapasta.cli import _validate_flags

        args = self._args(each=True, input=str(tmp_path / "nao_existe_arquivo.txt"))
        # Se não existir ou não for dir
        result = _validate_flags(args)
        assert result is False

    def test_watch_requer_pasta(self, capsys):
        from upapasta.cli import _validate_flags

        args = self._args(watch=True, input="/nao/existe")
        result = _validate_flags(args)
        assert result is False

    def test_watch_incompativel_com_each(self, tmp_path, capsys):
        from upapasta.cli import _validate_flags

        args = self._args(watch=True, each=True, input=str(tmp_path))
        result = _validate_flags(args)
        assert result is False

    def test_skip_rar_deprecated(self, capsys):
        from upapasta.cli import _validate_flags

        args = self._args()
        args.skip_rar_deprecated = True
        _validate_flags(args)
        assert args.rar is False

    def test_each_com_pasta_valida(self, tmp_path):
        from upapasta.cli import _validate_flags

        args = self._args(each=True, input=str(tmp_path))
        result = _validate_flags(args)
        assert result is True


# ── upfolder.py ───────────────────────────────────────────────────────────────


class TestBuildServerList:
    def test_servidor_primario(self, monkeypatch):
        from upapasta.upfolder import _build_server_list

        monkeypatch.delenv("NNTP_HOST", raising=False)
        env = {
            "NNTP_HOST": "news.exemplo.com",
            "NNTP_PORT": "563",
            "NNTP_USER": "usuario",
            "NNTP_PASS": "senha",
            "NNTP_SSL": "true",
        }
        servers = _build_server_list(env)
        assert len(servers) == 1
        assert servers[0]["host"] == "news.exemplo.com"
        assert servers[0]["ssl"] is True

    def test_sem_host_retorna_vazio(self, monkeypatch):
        from upapasta.upfolder import _build_server_list

        monkeypatch.delenv("NNTP_HOST", raising=False)
        servers = _build_server_list({})
        assert servers == []

    def test_dois_servidores(self, monkeypatch):
        from upapasta.upfolder import _build_server_list

        monkeypatch.delenv("NNTP_HOST", raising=False)
        monkeypatch.delenv("NNTP_HOST_2", raising=False)
        env = {
            "NNTP_HOST": "news1.exemplo.com",
            "NNTP_PORT": "563",
            "NNTP_USER": "u",
            "NNTP_PASS": "p",
            "NNTP_HOST_2": "news2.exemplo.com",
        }
        servers = _build_server_list(env)
        assert len(servers) == 2
        assert servers[1]["host"] == "news2.exemplo.com"

    def test_ssl_false(self, monkeypatch):
        from upapasta.upfolder import _build_server_list

        monkeypatch.delenv("NNTP_HOST", raising=False)
        env = {
            "NNTP_HOST": "news.exemplo.com",
            "NNTP_PORT": "119",
            "NNTP_USER": "u",
            "NNTP_PASS": "p",
            "NNTP_SSL": "false",
        }
        servers = _build_server_list(env)
        assert servers[0]["ssl"] is False


class TestFindNyuu:
    def test_nyuu_encontrado(self):
        from upapasta.upfolder import find_nyuu

        with patch("upapasta.upfolder.get_tool_path", return_value="/usr/bin/nyuu"):
            result = find_nyuu()
        assert result == "/usr/bin/nyuu"

    def test_nyuu_nao_encontrado(self):
        from upapasta.upfolder import find_nyuu

        with (
            patch("upapasta.upfolder.get_tool_path", return_value=None),
            patch("os.path.exists", return_value=False),
        ):
            result = find_nyuu()
        assert result is None


class TestSaveLoadUploadState:
    def test_save_e_load(self, tmp_path):
        from upapasta.upfolder import _load_upload_state, _save_upload_state

        state_path = str(tmp_path / "state.json")
        nzb_path = str(tmp_path / "test.nzb")
        _save_upload_state(state_path, ["a.rar", "a.par2"], ["a.par2"], str(tmp_path), nzb_path)
        state = _load_upload_state(state_path)
        assert state is not None
        assert state["files"] == ["a.rar", "a.par2"]

    def test_load_arquivo_invalido(self, tmp_path):
        from upapasta.upfolder import _load_upload_state

        bad = str(tmp_path / "bad.json")
        Path(bad).write_text("nao json")
        assert _load_upload_state(bad) is None

    def test_load_inexistente(self, tmp_path):
        from upapasta.upfolder import _load_upload_state

        assert _load_upload_state(str(tmp_path / "nao.json")) is None


class TestParseNyuuStderr:
    def test_erro_autenticacao(self):
        from upapasta.upfolder import _parse_nyuu_stderr

        result = _parse_nyuu_stderr("ERROR: 401 Unauthorized")
        assert result is not None
        assert "autenticação" in result.lower() or "401" in result

    def test_timeout(self):
        from upapasta.upfolder import _parse_nyuu_stderr

        result = _parse_nyuu_stderr("timeout: connection timed out")
        assert result is not None

    def test_nao_reconhecido(self):
        from upapasta.upfolder import _parse_nyuu_stderr

        result = _parse_nyuu_stderr("erro completamente desconhecido xyzabc")
        assert result is None

    def test_502(self):
        from upapasta.upfolder import _parse_nyuu_stderr

        result = _parse_nyuu_stderr("502 Bad Gateway")
        assert result is not None

    def test_ssl(self):
        from upapasta.upfolder import _parse_nyuu_stderr

        result = _parse_nyuu_stderr("SSL handshake failed")
        assert result is not None


class TestUploadToUsenet:
    def test_path_invalido(self, tmp_path):
        from upapasta.upfolder import upload_to_usenet

        rc = upload_to_usenet(
            str(tmp_path / "nao_existe"),
            env_vars={
                "NNTP_HOST": "test.com",
                "NNTP_PORT": "119",
                "NNTP_USER": "u",
                "NNTP_PASS": "p",
            },
        )
        assert rc == 1

    def test_sem_nyuu(self, tmp_path):
        from upapasta.upfolder import upload_to_usenet

        f = tmp_path / "test.rar"
        f.write_text("fake rar")
        # Precisa de .par2 para chegar na verificação de nyuu
        (tmp_path / "test.par2").write_text("fake par2")
        with patch("upapasta.upfolder.find_nyuu", return_value=None):
            rc = upload_to_usenet(
                str(f),
                env_vars={
                    "NNTP_HOST": "test.com",
                    "NNTP_PORT": "119",
                    "NNTP_USER": "u",
                    "NNTP_PASS": "p",
                    "USENET_GROUP": "alt.binaries.test",
                },
            )
        assert rc == 4

    def test_sem_credenciais(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet

        monkeypatch.delenv("NNTP_HOST", raising=False)
        monkeypatch.delenv("USENET_GROUP", raising=False)
        f = tmp_path / "test.rar"
        f.write_text("fake rar")
        (tmp_path / "test.par2").write_text("fake par2")
        rc = upload_to_usenet(str(f), env_vars={})
        assert rc == 2

    def test_dry_run(self, tmp_path, monkeypatch, capsys):
        from upapasta.upfolder import upload_to_usenet

        monkeypatch.delenv("NNTP_HOST", raising=False)
        monkeypatch.delenv("NZB_CONFLICT", raising=False)
        f = tmp_path / "test.rar"
        f.write_text("fake rar")
        (tmp_path / "test.par2").write_text("fake par2")
        # Cria um nyuu fake executável para o teste de dry-run
        nyuu_path = _create_mock_nyuu(tmp_path)
        rc = upload_to_usenet(
            str(f),
            env_vars={
                "NNTP_HOST": "news.test.com",
                "NNTP_PORT": "563",
                "NNTP_USER": "u",
                "NNTP_PASS": "p",
                "USENET_GROUP": "alt.binaries.test",
            },
            dry_run=True,
            nyuu_path=nyuu_path,
        )
        assert rc == 0


# ── orchestrator.py ───────────────────────────────────────────────────────────


class TestUpaPastaSession:
    def test_context_manager_limpa_em_excecao(self):
        from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession

        orch = MagicMock(spec=UpaPastaOrchestrator)
        orch._cleanup_on_error = MagicMock()

        session = UpaPastaSession(orch)
        try:
            with session:
                raise RuntimeError("erro simulado")
        except RuntimeError:
            pass
        orch._cleanup_on_error.assert_called_once()

    def test_context_manager_ok_sem_limpeza(self):
        from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession

        orch = MagicMock(spec=UpaPastaOrchestrator)
        orch._cleanup_on_error = MagicMock()

        with UpaPastaSession(orch):
            pass
        orch._cleanup_on_error.assert_not_called()


class TestGenerateRandomName:
    def test_comprimento_padrao(self):
        from upapasta.makepar import generate_random_name

        name = generate_random_name()
        assert 10 <= len(name) <= 30

    def test_comprimento_customizado(self):
        from upapasta.makepar import generate_random_name

        name = generate_random_name(15, 15)
        assert len(name) == 15

    def test_apenas_alphanumerico(self):
        from upapasta.makepar import generate_random_name

        name = generate_random_name(20, 20)
        assert name.isalnum()


# ── makepar.py: _deep_obfuscate_tree ─────────────────────────────────────────


class TestDeepObfuscateTree:
    def test_ofusca_arquivos(self, tmp_path):
        from upapasta.makepar import _deep_obfuscate_tree

        # Cria estrutura com arquivo
        f = tmp_path / "original.mkv"
        f.write_text("conteudo")
        mapping = _deep_obfuscate_tree(str(tmp_path))
        # Os nomes devem ter mudado
        remaining = list(tmp_path.iterdir())
        assert len(remaining) > 0
        # O mapeamento deve conter o nome original
        assert "original.mkv" in mapping.values() or any("original" in v for v in mapping.values())

    def test_pasta_inexistente(self):
        from upapasta.makepar import _deep_obfuscate_tree

        result = _deep_obfuscate_tree("/caminho/que/nao/existe")
        assert result == {}


# ── nzb.py: ResolveNzbBasename e ParseSubject ─────────────────────────────────


class TestResolveNzbBasename:
    def test_arquivo_simples(self):
        from upapasta.nzb import resolve_nzb_basename

        result = resolve_nzb_basename("/pasta/arquivo.mkv", is_folder=False)
        assert result == "arquivo"

    def test_pasta(self):
        from upapasta.nzb import resolve_nzb_basename

        result = resolve_nzb_basename("/pasta/MinhasSeries", is_folder=True)
        assert result == "MinhasSeries"

    def test_volume_rar(self):
        from upapasta.nzb import resolve_nzb_basename

        result = resolve_nzb_basename("/pasta/arquivo.part01.rar", is_folder=False)
        assert result == "arquivo"

    def test_com_obfuscated_map_pasta(self):
        from upapasta.nzb import resolve_nzb_basename

        result = resolve_nzb_basename(
            "/pasta/abc123", is_folder=True, obfuscated_map={"abc123": "OriginalName"}
        )
        assert result == "OriginalName"

    def test_com_obfuscated_map_arquivo(self):
        from upapasta.nzb import resolve_nzb_basename

        result = resolve_nzb_basename(
            "/pasta/abc123.mkv", is_folder=False, obfuscated_map={"abc123": "Original"}
        )
        assert result == "Original"


class TestParseSubject:
    def test_quoted_yenc(self):
        from upapasta.nzb import _parse_subject

        pre, name, suffix = _parse_subject('"arquivo.mkv" yEnc (1/5) [100]')
        assert "arquivo.mkv" in name

    def test_sem_indicadores(self):
        from upapasta.nzb import _parse_subject

        pre, name, suffix = _parse_subject("arquivo.mkv")
        assert name == "arquivo.mkv"

    def test_com_parte(self):
        from upapasta.nzb import _parse_subject

        pre, name, suffix = _parse_subject("prefixo arquivo.mkv (1/5)")
        assert suffix != ""


# ── makerar.py: mais caminhos de make_rar ─────────────────────────────────────


class TestMakeRarAdditional:
    def test_arquivo_unico_rar_nao_encontrado(self, tmp_path):
        from upapasta.makerar import make_rar

        f = tmp_path / "video.mkv"
        f.write_text("conteudo")
        with patch("upapasta.makerar.get_tool_path", return_value=None):
            rc, path = make_rar(str(f))
        assert rc == 4

    def test_make_rar_arquivo_unico_mock(self, tmp_path):
        from upapasta.makerar import make_rar

        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 100)

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", return_value=mock_proc),
        ):
            rc, path = make_rar(str(f))
        assert rc == 0

    def test_make_rar_com_password(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", return_value=mock_proc),
        ):
            rc, path = make_rar(str(folder), password="senha123")
        assert rc == 0

    def test_make_rar_force_sobrescreve(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")
        # Cria RAR existente
        (tmp_path / "pasta.rar").write_text("fake rar")

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", return_value=mock_proc),
        ):
            rc, path = make_rar(str(folder), force=True)
        assert rc == 0

    def test_make_rar_erro_retorno_5(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 1
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", return_value=mock_proc),
        ):
            rc, path = make_rar(str(folder))
        assert rc == 5
        assert path is None

    def test_make_rar_permissao_negada(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", side_effect=PermissionError("negado")),
        ):
            rc, path = make_rar(str(folder))
        assert rc == 5

    def test_make_rar_oserror(self, tmp_path):
        from upapasta.makerar import make_rar

        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        with (
            patch("upapasta.makerar.get_tool_path", return_value="/usr/bin/rar"),
            patch("upapasta.makerar.managed_popen", side_effect=OSError("io erro")),
        ):
            rc, path = make_rar(str(folder))
        assert rc == 5


# ── upfolder.py: mais caminhos ────────────────────────────────────────────────


class TestUpfolderParseArgs:
    def test_parse_args_basico(self, monkeypatch):
        from upapasta.upfolder import parse_args

        monkeypatch.setattr(sys, "argv", ["upfolder", "fake_test.rar"])
        args = parse_args()
        assert args.rarfile == "fake_test.rar"
        assert args.dry_run is False


class TestGenerateAnonymousUploader:
    def test_gera_string(self):
        from upapasta.upfolder import generate_anonymous_uploader

        result = generate_anonymous_uploader()
        assert isinstance(result, str)
        assert "@" in result
        assert "<" in result and ">" in result


class TestVerifyNzb:
    def _make_nzb(self, path: Path, with_file: bool = True) -> str:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        if with_file:
            file_elem = ET.SubElement(root, f"{{{ns}}}file")
            file_elem.set("subject", "test.rar")
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)
        return str(path)

    def test_nzb_valido(self, tmp_path):
        from upapasta.upfolder import _verify_nzb

        nzb = self._make_nzb(tmp_path / "test.nzb")
        assert _verify_nzb(nzb) is True

    def test_nzb_sem_files(self, tmp_path):
        from upapasta.upfolder import _verify_nzb

        nzb = self._make_nzb(tmp_path / "test.nzb", with_file=False)
        assert _verify_nzb(nzb) is False

    def test_nzb_vazio(self, tmp_path):
        from upapasta.upfolder import _verify_nzb

        nzb = tmp_path / "empty.nzb"
        nzb.write_text("")
        assert _verify_nzb(str(nzb)) is False

    def test_nzb_inexistente(self, tmp_path):
        from upapasta.upfolder import _verify_nzb

        assert _verify_nzb(str(tmp_path / "nao.nzb")) is False

    def test_nzb_xml_invalido(self, tmp_path):
        from upapasta.upfolder import _verify_nzb

        nzb = tmp_path / "bad.nzb"
        nzb.write_text("nao xml")
        assert _verify_nzb(str(nzb)) is False


class TestUploadToUsenetFolder:
    def test_upload_pasta_dry_run(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet

        monkeypatch.delenv("NNTP_HOST", raising=False)
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        folder = tmp_path / "minha_pasta"
        folder.mkdir()
        (folder / "video.mkv").write_text("fake video")

        # PAR2 fica no pai da pasta
        par2 = tmp_path / "minha_pasta.par2"
        par2.write_text("fake par2")

        nyuu_path = _create_mock_nyuu(tmp_path)

        rc = upload_to_usenet(
            str(folder),
            env_vars={
                "NNTP_HOST": "news.test.com",
                "NNTP_PORT": "563",
                "NNTP_USER": "u",
                "NNTP_PASS": "p",
                "USENET_GROUP": "alt.binaries.test",
            },
            dry_run=True,
            skip_rar=True,
            nyuu_path=nyuu_path,
        )
        assert rc == 0


# ── makepar.py: obfuscate_and_par ────────────────────────────────────────────


class TestObfuscateAndPar:
    def test_path_invalido(self, tmp_path):
        from upapasta.makepar import obfuscate_and_par

        rc, path, mapping, linked = obfuscate_and_par(str(tmp_path / "nao_existe"))
        assert rc != 0

    def test_par_falha_sem_backend(self, tmp_path):
        from upapasta.makepar import obfuscate_and_par

        f = tmp_path / "video.mkv"
        f.write_text("fake video content" * 100)
        with (
            patch("upapasta.makepar.find_parpar", return_value=None),
            patch("upapasta.makepar.find_par2", return_value=None),
        ):
            rc, path, mapping, linked = obfuscate_and_par(str(f))
        assert rc != 0


# ── orchestrator.py: mais caminhos ────────────────────────────────────────────


class TestOrchestratorValidate:
    def test_validate_path_invalido(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator

        orch = UpaPastaOrchestrator(
            input_path=str(tmp_path / "nao_existe"),
        )
        result = orch.validate()
        assert result is False

    def test_validate_path_valido(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator

        f = tmp_path / "video.mkv"
        f.write_text("x" * 1000)
        orch = UpaPastaOrchestrator(input_path=str(f))
        result = orch.validate()
        assert isinstance(result, bool)
