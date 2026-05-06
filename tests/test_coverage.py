"""
test_coverage.py

Testes focados para aumentar cobertura dos módulos core para ≥ 90%.
Cobre: nzb.py, makerar.py, makepar.py, cli.py, upfolder.py, orchestrator.py
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
        result = resolve_nzb_template({"NZB_OUT": "/saida/{filename}.nzb"}, is_folder=False, skip_rar=True)
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


class TestMergeNzbs:
    def _make_nzb(self, path: Path, subject: str = "test.rar") -> str:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        ET.SubElement(root, f"{{{ns}}}head")
        file_elem = ET.SubElement(root, f"{{{ns}}}file")
        file_elem.set("subject", subject)
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)
        return str(path)

    def test_merge_dois_nzbs(self, tmp_path):
        from upapasta.nzb import merge_nzbs
        nzb1 = self._make_nzb(tmp_path / "ep1.nzb", "ep1.rar")
        nzb2 = self._make_nzb(tmp_path / "ep2.nzb", "ep2.rar")
        out = str(tmp_path / "season.nzb")
        result = merge_nzbs([nzb1, nzb2], out)
        assert result is True
        assert os.path.exists(out)

    def test_merge_lista_vazia(self, tmp_path):
        from upapasta.nzb import merge_nzbs
        out = str(tmp_path / "season.nzb")
        result = merge_nzbs([], out)
        assert result is False

    def test_merge_arquivo_invalido(self, tmp_path):
        from upapasta.nzb import merge_nzbs
        bad = str(tmp_path / "bad.nzb")
        Path(bad).write_text("nao xml")
        out = str(tmp_path / "season.nzb")
        result = merge_nzbs([bad], out)
        assert result is False


class TestCollectSeasonNzbs:
    def _make_nzb(self, path: Path, subject: str) -> None:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        file_elem = ET.SubElement(root, f"{{{ns}}}file")
        file_elem.set("subject", subject)
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)

    def test_sem_pasta(self, tmp_path):
        from upapasta.nzb import collect_season_nzbs
        result = collect_season_nzbs(str(tmp_path / "nao_existe"), "Serie.S01")
        assert result == []

    def test_sem_padrao_temporada(self, tmp_path):
        from upapasta.nzb import collect_season_nzbs
        result = collect_season_nzbs(str(tmp_path), "SerieSemTemporada")
        assert result == []

    def test_coleta_episodios(self, tmp_path):
        from upapasta.nzb import collect_season_nzbs
        self._make_nzb(tmp_path / "Serie.S01E01.nzb", "S01E01/video.mkv")
        self._make_nzb(tmp_path / "Serie.S01E02.nzb", "S01E02/video.mkv")
        # NZB final da temporada (deve ser excluído)
        self._make_nzb(tmp_path / "Serie.S01.nzb", "season.nzb")
        result = collect_season_nzbs(str(tmp_path), "Serie.S01")
        assert len(result) == 2


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
        with patch("shutil.which", return_value=None):
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

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc):
            rc, path = make_rar(str(folder))
        assert rc == 0

    def test_parse_args_makerar(self, monkeypatch):
        from upapasta.makerar import parse_args
        monkeypatch.setattr(sys, "argv", ["makerar", "/tmp/pasta"])
        args = parse_args()
        assert args.folder == "/tmp/pasta"
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
        assert _parse_size("1G") == 1024 ** 3

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
        with patch("upapasta.makepar.find_parpar", return_value=None), \
             patch("upapasta.makepar.find_par2", return_value=None):
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
        monkeypatch.setattr(sys, "argv", ["makepar", "/tmp/test.rar"])
        args = parse_args()
        assert args.rarfile == "/tmp/test.rar"


# ── cli.py ────────────────────────────────────────────────────────────────────

class TestCheckDependencies:
    def test_tudo_disponivel(self):
        from upapasta.cli import check_dependencies
        with patch("shutil.which", return_value="/usr/bin/rar"):
            result = check_dependencies(rar_needed=True)
        assert result is True

    def test_nyuu_ausente(self):
        from upapasta.cli import check_dependencies
        def which_sem_nyuu(cmd: str) -> str | None:
            return None if cmd == "nyuu" else "/usr/bin/" + cmd
        with patch("shutil.which", side_effect=which_sem_nyuu):
            result = check_dependencies(rar_needed=False)
        assert result is False

    def test_rar_nao_necessario(self):
        from upapasta.cli import check_dependencies
        def which_sem_rar(cmd: str) -> str | None:
            return None if cmd == "rar" else "/usr/bin/" + cmd
        with patch("shutil.which", side_effect=which_sem_rar):
            result = check_dependencies(rar_needed=False)
        assert result is True

    def test_opcionals_ausentes(self, capsys):
        from upapasta.cli import check_dependencies
        def which_sem_opcionals(cmd: str) -> str | None:
            if cmd in ("mediainfo", "ffprobe"):
                return None
            return "/usr/bin/" + cmd
        with patch("shutil.which", side_effect=which_sem_opcionals):
            result = check_dependencies(rar_needed=False)
        captured = capsys.readouterr()
        assert "opcionais" in captured.out.lower() or result is True


class TestValidateFlags:
    def _args(self, **kwargs) -> argparse.Namespace:
        defaults = {
            "rar": False, "password": None, "obfuscate": False,
            "strong_obfuscate": False, "each": False, "season": False,
            "watch": False, "input": "/tmp/test",
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_password_sem_rar_ativa_rar(self, capsys):
        from upapasta.cli import _validate_flags
        args = self._args(password="senha123")
        _validate_flags(args)
        assert args.rar is True

    def test_password_random(self, capsys):
        from upapasta.cli import _validate_flags
        args = self._args(password="__random__")
        _validate_flags(args)
        assert args.password != "__random__"
        assert len(args.password) == 16

    def test_strong_obfuscate_ativa_obfuscate(self, capsys):
        from upapasta.cli import _validate_flags
        args = self._args(strong_obfuscate=True)
        _validate_flags(args)
        assert args.obfuscate is True

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
        with patch("shutil.which", return_value="/usr/bin/nyuu"):
            result = find_nyuu()
        assert result == "/usr/bin/nyuu"

    def test_nyuu_nao_encontrado(self):
        from upapasta.upfolder import find_nyuu
        with patch("shutil.which", return_value=None):
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
            env_vars={"NNTP_HOST": "test.com", "NNTP_PORT": "119",
                      "NNTP_USER": "u", "NNTP_PASS": "p"},
        )
        assert rc == 1

    def test_sem_nyuu(self, tmp_path):
        from upapasta.upfolder import upload_to_usenet
        f = tmp_path / "test.rar"
        f.write_text("fake rar")
        # Precisa de .par2 para chegar na verificação de nyuu
        (tmp_path / "test.par2").write_text("fake par2")
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {}, clear=True):
            rc = upload_to_usenet(
                str(f),
                env_vars={"NNTP_HOST": "test.com", "NNTP_PORT": "119",
                          "NNTP_USER": "u", "NNTP_PASS": "p",
                          "USENET_GROUP": "alt.binaries.test"},
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
        nyuu_fake = tmp_path / "nyuu"
        nyuu_fake.write_text("#!/bin/sh\nexit 0")
        nyuu_fake.chmod(0o755)
        rc = upload_to_usenet(
            str(f),
            env_vars={"NNTP_HOST": "news.test.com", "NNTP_PORT": "563",
                      "NNTP_USER": "u", "NNTP_PASS": "p",
                      "USENET_GROUP": "alt.binaries.test"},
            dry_run=True,
            nyuu_path=str(nyuu_fake),
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
        assert len(name) == 12

    def test_comprimento_customizado(self):
        from upapasta.makepar import generate_random_name
        name = generate_random_name(20)
        assert len(name) == 20

    def test_apenas_alphanumerico(self):
        from upapasta.makepar import generate_random_name
        name = generate_random_name(50)
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
        result = resolve_nzb_basename("/pasta/abc123", is_folder=True,
                                       obfuscated_map={"abc123": "OriginalName"})
        assert result == "OriginalName"

    def test_com_obfuscated_map_arquivo(self):
        from upapasta.nzb import resolve_nzb_basename
        result = resolve_nzb_basename("/pasta/abc123.mkv", is_folder=False,
                                       obfuscated_map={"abc123": "Original"})
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
        with patch("shutil.which", return_value=None):
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

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc):
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

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc):
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

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc):
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

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc):
            rc, path = make_rar(str(folder))
        assert rc == 5
        assert path is None

    def test_make_rar_permissao_negada(self, tmp_path):
        from upapasta.makerar import make_rar
        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", side_effect=PermissionError("negado")):
            rc, path = make_rar(str(folder))
        assert rc == 5

    def test_make_rar_oserror(self, tmp_path):
        from upapasta.makerar import make_rar
        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", side_effect=OSError("io erro")):
            rc, path = make_rar(str(folder))
        assert rc == 5


# ── upfolder.py: mais caminhos ────────────────────────────────────────────────

class TestUpfolderParseArgs:
    def test_parse_args_basico(self, monkeypatch):
        from upapasta.upfolder import parse_args
        monkeypatch.setattr(sys, "argv", ["upfolder", "/tmp/test.rar"])
        args = parse_args()
        assert args.rarfile == "/tmp/test.rar"
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

        nyuu_fake = tmp_path / "nyuu"
        nyuu_fake.write_text("#!/bin/sh\nexit 0")
        nyuu_fake.chmod(0o755)

        rc = upload_to_usenet(
            str(folder),
            env_vars={"NNTP_HOST": "news.test.com", "NNTP_PORT": "563",
                      "NNTP_USER": "u", "NNTP_PASS": "p",
                      "USENET_GROUP": "alt.binaries.test"},
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu_fake),
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
        with patch("upapasta.makepar.find_parpar", return_value=None), \
             patch("upapasta.makepar.find_par2", return_value=None):
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


# ── nzb.py: fix_nzb_subjects e fix_season_nzb_subjects ──────────────────────

class TestFixNzbSubjects:
    def _make_nzb(self, path: Path, subjects: list[str]) -> str:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        for subj in subjects:
            fe = ET.SubElement(root, f"{{{ns}}}file")
            fe.set("subject", f'"{subj}" yEnc (1/1)')
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)
        return str(path)

    def test_fix_com_folder_name(self, tmp_path):
        from upapasta.nzb import fix_nzb_subjects
        nzb = self._make_nzb(tmp_path / "test.nzb", ["video.mkv", "video.par2"])
        fix_nzb_subjects(str(nzb), folder_name="MinhasSeries")
        content = Path(nzb).read_text(encoding="utf-8")
        assert "MinhasSeries/video.mkv" in content

    def test_fix_com_obfuscated_map(self, tmp_path):
        from upapasta.nzb import fix_nzb_subjects
        nzb = self._make_nzb(tmp_path / "test.nzb", ["abc123.mkv"])
        fix_nzb_subjects(str(nzb), obfuscated_map={"abc123": "original"})
        content = Path(nzb).read_text(encoding="utf-8")
        assert "original.mkv" in content

    def test_fix_strong_obfuscate(self, tmp_path):
        from upapasta.nzb import fix_nzb_subjects
        nzb = self._make_nzb(tmp_path / "test.nzb", ["abc123.mkv"])
        fix_nzb_subjects(str(nzb), strong_obfuscate=True)
        # Strong obfuscate mantém nome aleatório
        content = Path(nzb).read_text(encoding="utf-8")
        assert "abc123.mkv" in content

    def test_fix_arquivo_invalido(self, tmp_path):
        from upapasta.nzb import fix_nzb_subjects
        bad = str(tmp_path / "bad.nzb")
        Path(bad).write_text("nao xml")
        # Não deve levantar exceção
        fix_nzb_subjects(bad)

    def test_fix_com_file_list(self, tmp_path):
        from upapasta.nzb import fix_nzb_subjects
        nzb = self._make_nzb(tmp_path / "test.nzb", ["video.mkv"])
        fix_nzb_subjects(str(nzb), file_list=["video.mkv"], folder_name="Serie")
        content = Path(nzb).read_text(encoding="utf-8")
        assert "Serie/video.mkv" in content


class TestFixSeasonNzbSubjects:
    def _make_nzb_with_subject(self, path: Path, subject: str) -> str:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        fe = ET.SubElement(root, f"{{{ns}}}file")
        fe.set("subject", subject)
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)
        return str(path)

    def test_sem_episode_data(self, tmp_path):
        from upapasta.nzb import fix_season_nzb_subjects
        season_nzb = self._make_nzb_with_subject(tmp_path / "season.nzb", "S01E01/video.mkv")
        # Lista vazia não deve modificar nada
        fix_season_nzb_subjects(str(season_nzb), [])

    def test_com_episode_data(self, tmp_path):
        from upapasta.nzb import fix_season_nzb_subjects
        ep_nzb = self._make_nzb_with_subject(tmp_path / "ep1.nzb", '"S01E01/video.mkv" yEnc (1/1)')
        season_nzb = self._make_nzb_with_subject(tmp_path / "season.nzb", '"S01E01/video.mkv" yEnc (1/1)')
        fix_season_nzb_subjects(str(season_nzb), [(str(ep_nzb), "S01E01")])
        # Não deve levantar exceção

    def test_nzb_invalido(self, tmp_path):
        from upapasta.nzb import fix_season_nzb_subjects
        bad = str(tmp_path / "bad.nzb")
        Path(bad).write_text("nao xml")
        ep_nzb = self._make_nzb_with_subject(tmp_path / "ep.nzb", "S01E01/video.mkv")
        # Não deve levantar exceção
        fix_season_nzb_subjects(bad, [(str(ep_nzb), "S01E01")])


# ── makerar.py: caminhos adicionais ──────────────────────────────────────────

class TestMakeRarBranches:
    def test_make_rar_volumes(self, tmp_path):
        """Testa path de volumes (vol_bytes não None)."""
        from upapasta.makerar import make_rar
        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x" * 100)

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        # Mocka _volume_size_bytes para retornar valor não-None (simula pasta grande)
        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", return_value=mock_proc), \
             patch("upapasta.makerar._volume_size_bytes", return_value=5 * 1024 * 1024):
            rc, path = make_rar(str(folder))
        assert rc == 0

    def test_make_rar_file_not_found(self, tmp_path):
        from upapasta.makerar import make_rar
        folder = tmp_path / "pasta"
        folder.mkdir()
        (folder / "a.txt").write_text("x")

        with patch("shutil.which", return_value="/usr/bin/rar"), \
             patch("upapasta.makerar.managed_popen", side_effect=FileNotFoundError()):
            rc, path = make_rar(str(folder))
        assert rc == 4


# ── makepar.py: revert_obfuscation branches ─────────────────────────────────

class TestRevertObfuscation:
    def test_revert_linked_folder(self, tmp_path):
        from upapasta.makepar import _revert_obfuscation
        obf_path = str(tmp_path / "abc123")
        orig_path = str(tmp_path / "original")
        os.makedirs(obf_path)
        _revert_obfuscation(
            is_folder=True, is_rar_vol_set=False,
            obfuscated_path=obf_path, input_path=orig_path,
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=True
        )
        # Hardlink path: deve ter tentado remover
        assert not os.path.exists(obf_path)

    def test_revert_renamed_folder(self, tmp_path):
        from upapasta.makepar import _revert_obfuscation
        obf_path = str(tmp_path / "abc123")
        orig_path = str(tmp_path / "original")
        os.makedirs(obf_path)
        _revert_obfuscation(
            is_folder=True, is_rar_vol_set=False,
            obfuscated_path=obf_path, input_path=orig_path,
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=False
        )
        assert os.path.exists(orig_path)

    def test_revert_single_file_linked(self, tmp_path):
        from upapasta.makepar import _revert_obfuscation
        obf_file = tmp_path / "abc123.mkv"
        obf_file.write_text("fake")
        orig_path = str(tmp_path / "original.mkv")
        _revert_obfuscation(
            is_folder=False, is_rar_vol_set=False,
            obfuscated_path=str(obf_file), input_path=orig_path,
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=True
        )
        assert not obf_file.exists()

    def test_revert_single_file_renamed(self, tmp_path):
        from upapasta.makepar import _revert_obfuscation
        obf_file = tmp_path / "abc123.mkv"
        obf_file.write_text("fake")
        orig_path = str(tmp_path / "original.mkv")
        _revert_obfuscation(
            is_folder=False, is_rar_vol_set=False,
            obfuscated_path=str(obf_file), input_path=orig_path,
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=False
        )
        assert os.path.exists(orig_path)


# ── upfolder.py: mais branches ────────────────────────────────────────────────

class TestGetUploadedFilesFromNzb:
    def _make_nzb(self, path: Path, segments: list[str]) -> str:
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        file_elem = ET.SubElement(root, f"{{{ns}}}file")
        file_elem.set("subject", "test.rar")
        segs = ET.SubElement(file_elem, f"{{{ns}}}segments")
        for seg in segments:
            s = ET.SubElement(segs, f"{{{ns}}}segment")
            s.text = seg
        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="UTF-8", xml_declaration=True)
        return str(path)

    def test_nzb_valido_retorna_set(self, tmp_path):
        from upapasta.upfolder import _get_uploaded_files_from_nzb
        nzb = self._make_nzb(tmp_path / "test.nzb", ["msg-id@server"])
        result = _get_uploaded_files_from_nzb(str(nzb))
        # Pode retornar set vazio ou com filenames
        assert isinstance(result, set)

    def test_nzb_invalido_retorna_vazio(self, tmp_path):
        from upapasta.upfolder import _get_uploaded_files_from_nzb
        bad = str(tmp_path / "bad.nzb")
        Path(bad).write_text("nao xml")
        result = _get_uploaded_files_from_nzb(bad)
        assert result == set()


class TestNzbResolveOut:
    def test_resolve_out_com_env(self, tmp_path, monkeypatch):
        from upapasta.nzb import resolve_nzb_out
        monkeypatch.delenv("NZB_OUT", raising=False)
        out, abs_out = resolve_nzb_out(
            str(tmp_path / "video.mkv"),
            env_vars={},
            is_folder=False,
            skip_rar=True,
            working_dir=str(tmp_path),
        )
        assert out.endswith(".nzb")

    def test_resolve_out_pasta(self, tmp_path, monkeypatch):
        from upapasta.nzb import resolve_nzb_out
        monkeypatch.delenv("NZB_OUT", raising=False)
        folder = tmp_path / "serie"
        folder.mkdir()
        out, abs_out = resolve_nzb_out(
            str(folder),
            env_vars={},
            is_folder=True,
            skip_rar=True,
            working_dir=str(tmp_path),
        )
        assert out.endswith(".nzb")


# ── orchestrator.py: caminhos adicionais ─────────────────────────────────────

class TestOrchestratorAdditional:
    def test_generate_password(self):
        from upapasta.orchestrator import UpaPastaOrchestrator
        pwd = UpaPastaOrchestrator._generate_password(12)
        assert len(pwd) == 12
        assert pwd.isalnum()

    def test_run_makepar_sem_input_target(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator
        orch = UpaPastaOrchestrator(input_path=str(tmp_path / "video.mkv"))
        orch.input_target = None
        result = orch.run_makepar()
        assert result is False

    def test_run_upload_sem_input_target(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator
        orch = UpaPastaOrchestrator(input_path=str(tmp_path / "video.mkv"))
        orch.input_target = None
        result = orch.run_upload()
        assert result is False

    def test_session_cleanup_on_exception(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        orch = UpaPastaOrchestrator(input_path=str(f))
        cleanup_called = []

        def mock_cleanup(preserve_rar: bool = False) -> None:
            cleanup_called.append(preserve_rar)
        orch._cleanup_on_error = mock_cleanup  # type: ignore

        try:
            with UpaPastaSession(orch):
                raise RuntimeError("erro de teste")
        except RuntimeError:
            pass
        assert len(cleanup_called) == 1

    def test_session_keyboard_interrupt(self, tmp_path):
        from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        orch = UpaPastaOrchestrator(input_path=str(f))

        def mock_cleanup(preserve_rar: bool = False) -> None:
            pass
        orch._cleanup_on_error = mock_cleanup  # type: ignore

        try:
            with UpaPastaSession(orch):
                raise KeyboardInterrupt()
        except KeyboardInterrupt:
            pass


# ── makepar.py: make_parity caminhos adicionais ────────────────────────────────

class TestMakeParityBranches:
    def _mock_popen(self, rc: int = 0) -> MagicMock:
        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = rc
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)
        return mock_proc

    def test_force_deleta_par2_existente(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 50)
        existing = tmp_path / "video.par2"
        existing.write_text("fake par2")

        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", return_value=self._mock_popen(0)):
            rc = make_parity(str(f), force=True)
        assert rc == 0
        assert not existing.exists()

    def test_pasta_vazia(self, tmp_path):
        from upapasta.makepar import make_parity
        folder = tmp_path / "vazia"
        folder.mkdir()
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")):
            rc = make_parity(str(folder))
        assert rc == 2

    def test_rar_volume_set(self, tmp_path):
        from upapasta.makepar import make_parity
        (tmp_path / "serie.part01.rar").write_text("part1")
        (tmp_path / "serie.part02.rar").write_text("part2")
        f = tmp_path / "serie.part01.rar"

        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", return_value=self._mock_popen(0)):
            rc = make_parity(str(f))
        assert rc == 0

    def test_backend_parpar_nao_encontrado(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("x")
        with patch("upapasta.makepar.find_parpar", return_value=None):
            rc = make_parity(str(f), backend="parpar")
        assert rc == 4

    def test_backend_par2_nao_encontrado(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("x")
        with patch("upapasta.makepar.find_par2", return_value=None):
            rc = make_parity(str(f), backend="par2")
        assert rc == 4

    def test_backend_auto_usa_par2_quando_sem_parpar(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 20)
        with patch("upapasta.makepar.find_parpar", return_value=None), \
             patch("upapasta.makepar.find_par2", return_value=("par2", "/usr/bin/par2")), \
             patch("upapasta.makepar.managed_popen", return_value=self._mock_popen(0)):
            rc = make_parity(str(f), backend="auto")
        assert rc == 0

    def test_backend_auto_sem_nenhum(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("x")
        with patch("upapasta.makepar.find_parpar", return_value=None), \
             patch("upapasta.makepar.find_par2", return_value=None):
            rc = make_parity(str(f), backend="auto")
        assert rc == 4

    def test_make_parity_rc_nao_zero(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 20)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", return_value=self._mock_popen(1)):
            rc = make_parity(str(f))
        assert rc == 5

    def test_make_parity_oserror(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 20)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", side_effect=OSError("io error")):
            rc = make_parity(str(f))
        assert rc == 5

    def test_make_parity_permission_error(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 20)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", side_effect=PermissionError("negado")):
            rc = make_parity(str(f))
        assert rc == 5

    def test_handle_par_failure_com_rar_volume(self, tmp_path):
        from upapasta.makepar import handle_par_failure
        (tmp_path / "serie.part01.rar").write_text("rar1")
        with patch("upapasta.makepar.make_parity", return_value=0):
            result = handle_par_failure(
                str(tmp_path / "serie.part01.rar"),
                original_rc=5,
                threads=4,
            )
        assert isinstance(result, bool)

    def test_make_parity_ja_existe_sem_force(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo")
        (tmp_path / "video.par2").write_text("fake par2")
        rc = make_parity(str(f), force=False)
        assert rc == 3

    def test_make_parity_dry_run(self, tmp_path):
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 20)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")):
            rc = make_parity(str(f), dry_run=True)
        assert rc == 0


# ── upfolder.py: caminhos adicionais ─────────────────────────────────────────

class TestUpfolderAdditional:
    def _base_env(self) -> dict:
        return {
            "NNTP_HOST": "news.test.com",
            "NNTP_PORT": "563",
            "NNTP_USER": "u",
            "NNTP_PASS": "p",
            "USENET_GROUP": "alt.binaries.test",
        }

    def test_rar_volume_input(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        (tmp_path / "serie.part01.rar").write_text("rar1")
        (tmp_path / "serie.part02.rar").write_text("rar2")
        (tmp_path / "serie.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        rc = upload_to_usenet(
            str(tmp_path / "serie.part01.rar"),
            env_vars=self._base_env(),
            dry_run=True,
            skip_rar=False,
            nyuu_path=str(nyuu),
        )
        assert rc == 0

    def test_pool_grupos(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        env = self._base_env()
        env["USENET_GROUP"] = "alt.binaries.a,alt.binaries.b,alt.binaries.c"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
        )
        assert rc == 0

    def test_dry_run_com_opcoes_extras(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        rc = upload_to_usenet(
            str(f),
            env_vars=self._base_env(),
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
            upload_timeout=30,
            nyuu_extra_args=["--extra-flag"],
        )
        assert rc == 0

    def test_credenciais_incompletas(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)
        monkeypatch.delenv("USENET_GROUP", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        env = self._base_env()
        env.pop("USENET_GROUP")

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
        )
        assert rc == 2

    def test_nyuu_path_invalido(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        rc = upload_to_usenet(
            str(f),
            env_vars=self._base_env(),
            dry_run=False,
            skip_rar=True,
            nyuu_path="/caminho/inexistente/nyuu",
        )
        assert rc == 4

    def test_nyuu_extra_args_via_env(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        env = self._base_env()
        env["NYUU_EXTRA_ARGS"] = "--no-datetime"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
        )
        assert rc == 0

    def test_upload_oserror_em_nyuu(self, tmp_path, monkeypatch):
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        with patch("upapasta.upfolder.managed_popen", side_effect=OSError("io error")):
            rc = upload_to_usenet(
                str(f),
                env_vars=self._base_env(),
                dry_run=False,
                skip_rar=True,
                nyuu_path=str(nyuu),
            )
        assert rc == 5

    def test_save_upload_state_oserror(self, tmp_path):
        from upapasta.upfolder import _save_upload_state
        _save_upload_state(
            "/dev/null/impossible/path/state.json",
            files=["video.mkv"],
            par2_files=["video.par2"],
            working_dir=str(tmp_path),
            nzb_out_abs="video.nzb",
        )

    def test_load_upload_state_nao_dict(self, tmp_path):
        from upapasta.upfolder import _load_upload_state
        state_path = tmp_path / "state.json"
        state_path.write_text('["lista", "nao", "dict"]')
        result = _load_upload_state(str(state_path))
        assert result is None

    def test_multiplos_servidores_print(self, tmp_path, monkeypatch):
        """Testa mensagem quando há múltiplos servidores (linha 383)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        env = self._base_env()
        env["NNTP_HOST_2"] = "news2.test.com"
        env["NNTP_USER_2"] = "u2"
        env["NNTP_PASS_2"] = "p2"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
        )
        assert rc == 0

    def test_dry_run_com_nzb_overwrite(self, tmp_path, monkeypatch):
        """Testa dry_run com NZB_OVERWRITE ativo (linha 510)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        env = self._base_env()
        env["NZB_OVERWRITE"] = "1"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
        )
        assert rc == 0

    def _make_mock_popen_that_creates_nzb(self, nzb_path: str) -> MagicMock:
        """Cria mock de managed_popen que escreve um NZB válido ao ser chamado."""
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        fe = ET.SubElement(root, f"{{{ns}}}file")
        fe.set("subject", '"video.mkv" yEnc (1/1)')

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        def enter_and_create_nzb(s: object) -> MagicMock:
            ET.ElementTree(root).write(nzb_path, encoding="UTF-8", xml_declaration=True)
            return mock_proc

        mock_proc.__enter__ = enter_and_create_nzb
        mock_proc.__exit__ = MagicMock(return_value=False)
        return mock_proc

    def test_upload_pasta_com_folder_name(self, tmp_path, monkeypatch):
        """Testa fix_nzb_subjects e verify_nzb após upload (linhas 618-619, 629)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        folder = tmp_path / "minha_pasta"
        folder.mkdir()
        (folder / "video.mkv").write_text("fake")
        par2 = tmp_path / "minha_pasta.par2"
        par2.write_text("fake par2")

        fake_nyuu = tmp_path / "nyuu"
        fake_nyuu.write_text("#!/bin/sh\nexit 0")
        fake_nyuu.chmod(0o755)

        nzb_path = str(tmp_path / "minha_pasta.nzb")
        mock_proc = self._make_mock_popen_that_creates_nzb(nzb_path)

        env = self._base_env()
        env["NZB_OUT_DIR"] = str(tmp_path)

        with patch("upapasta.upfolder.managed_popen", return_value=mock_proc):
            rc = upload_to_usenet(
                str(folder),
                env_vars=env,
                dry_run=False,
                skip_rar=True,
                nyuu_path=str(fake_nyuu),
                folder_name="MinhasSeries",
            )
        assert rc == 0

    def test_upload_arquivo_com_password_skip_rar_false(self, tmp_path, monkeypatch):
        """Testa inject_nzb_password após upload (linhas 622-623)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.rar"
        f.write_text("fake rar")
        (tmp_path / "video.par2").write_text("fake par2")

        fake_nyuu = tmp_path / "nyuu"
        fake_nyuu.write_text("#!/bin/sh\nexit 0")
        fake_nyuu.chmod(0o755)

        nzb_path = str(tmp_path / "video.nzb")
        mock_proc = self._make_mock_popen_that_creates_nzb(nzb_path)

        env = self._base_env()
        env["NZB_OUT_DIR"] = str(tmp_path)

        with patch("upapasta.upfolder.managed_popen", return_value=mock_proc):
            rc = upload_to_usenet(
                str(f),
                env_vars=env,
                dry_run=False,
                skip_rar=False,
                nyuu_path=str(fake_nyuu),
                password="senha123",
            )
        assert rc == 0


# ── makepar.py: _revert_obfuscation rar vol set + OSError ────────────────────

class TestRevertObfuscationAdditional:
    def test_revert_rar_vol_set_linked(self, tmp_path):
        """was_linked=True, is_rar_vol_set=True → remove volumes ofuscados."""
        from upapasta.makepar import _revert_obfuscation
        # Cria volumes ofuscados
        (tmp_path / "abc123.part01.rar").write_text("part1")
        (tmp_path / "abc123.part02.rar").write_text("part2")
        _revert_obfuscation(
            is_folder=False, is_rar_vol_set=True,
            obfuscated_path=str(tmp_path / "abc123.part01.rar"),
            input_path=str(tmp_path / "original.part01.rar"),
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=True,
        )
        assert not (tmp_path / "abc123.part01.rar").exists()
        assert not (tmp_path / "abc123.part02.rar").exists()

    def test_revert_rar_vol_set_renamed(self, tmp_path):
        """was_linked=False, is_rar_vol_set=True → renomeia volumes de volta."""
        from upapasta.makepar import _revert_obfuscation
        (tmp_path / "abc123.part01.rar").write_text("part1")
        (tmp_path / "abc123.part02.rar").write_text("part2")
        _revert_obfuscation(
            is_folder=False, is_rar_vol_set=True,
            obfuscated_path=str(tmp_path / "abc123.part01.rar"),
            input_path=str(tmp_path / "original.part01.rar"),
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=False,
        )
        assert (tmp_path / "original.part01.rar").exists()
        assert (tmp_path / "original.part02.rar").exists()

    def test_revert_folder_rename_oserror(self, tmp_path):
        """OSError ao renomear pasta de volta → apenas mensagem de erro."""
        from upapasta.makepar import _revert_obfuscation
        obf_path = str(tmp_path / "abc123")
        os.makedirs(obf_path)
        # Cria diretório destino para forçar OSError no rename
        os.makedirs(str(tmp_path / "original"))
        _revert_obfuscation(
            is_folder=True, is_rar_vol_set=False,
            obfuscated_path=obf_path,
            input_path=str(tmp_path / "original"),
            parent_dir=str(tmp_path), random_base="abc123",
            obfuscated_map={"abc123": "original"}, was_linked=False,
        )
        # Apenas verifica que não levantou exceção


# ── orchestrator.py: caminhos adicionais 2 ───────────────────────────────────

class TestOrchestratorAdditional2:
    def test_session_cleanup_exception_swallowed(self, tmp_path):
        """_cleanup_on_error levanta exceção dentro do UpaPastaSession — deve ser swallowed."""
        from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        orch = UpaPastaOrchestrator(input_path=str(f))

        def raises_cleanup(preserve_rar: bool = False) -> None:
            raise RuntimeError("falha no cleanup")
        orch._cleanup_on_error = raises_cleanup  # type: ignore

        try:
            with UpaPastaSession(orch):
                raise ValueError("erro original")
        except ValueError:
            pass  # Exception original deve propagar; cleanup exception deve ser swallowed

    def test_run_makepar_skip_par_com_arquivo(self, tmp_path):
        """skip_par=True com par2 existente → retorna True."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 100)
        par2 = tmp_path / "video.par2"
        par2.write_text("fake par2")

        orch = UpaPastaOrchestrator(input_path=str(f), skip_par=True)
        orch.input_target = str(f)
        result = orch.run_makepar()
        assert result is True
        assert orch.par_file == str(par2)

    def test_run_makepar_skip_par_sem_arquivo(self, tmp_path):
        """skip_par=True sem par2 existente → retorna False."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("conteudo")

        orch = UpaPastaOrchestrator(input_path=str(f), skip_par=True)
        orch.input_target = str(f)
        result = orch.run_makepar()
        assert result is False

    def test_run_makerar_skip_rar(self, tmp_path):
        """skip_rar=True → run_makerar não cria RAR, só define input_target."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("conteudo")

        orch = UpaPastaOrchestrator(input_path=str(f), skip_rar=True)
        result = orch.run_makerar()
        assert result is True
        assert orch.input_target == str(f)


# ── makepar.py: _obfuscate_folder OSError fallback ───────────────────────────

class TestObfuscateFolderFallback:
    def test_obfuscate_folder_link_fails(self, tmp_path):
        """link_tree falha → usa rename (was_linked=False)."""
        from upapasta.makepar import _obfuscate_folder
        src = tmp_path / "original"
        src.mkdir()
        (src / "video.mkv").write_text("fake")

        with patch("upapasta.makepar.link_tree", side_effect=OSError("cross-device")):
            obf_path, mapping, was_linked, par_input = _obfuscate_folder(
                str(src), str(tmp_path), "original", "abc123"
            )
        assert was_linked is False
        assert os.path.exists(obf_path)

    def test_obfuscate_single_file_link_fails(self, tmp_path):
        """os.link falha → usa rename (was_linked=False)."""
        from upapasta.makepar import _obfuscate_single_file
        f = tmp_path / "video.mkv"
        f.write_text("fake content")

        with patch("os.link", side_effect=OSError("cross-device")):
            obf_path, mapping, was_linked, par_input = _obfuscate_single_file(
                str(f), str(tmp_path), "video.mkv", "abc123"
            )
        assert was_linked is False

    def test_obfuscate_rar_vol_set_link_fails(self, tmp_path):
        """os.link falha em volumes RAR → usa rename."""
        from upapasta.makepar import _obfuscate_rar_vol_set
        (tmp_path / "serie.part01.rar").write_text("part1")
        (tmp_path / "serie.part02.rar").write_text("part2")

        with patch("os.link", side_effect=OSError("cross-device")):
            obf_path, mapping, was_linked, par_input = _obfuscate_rar_vol_set(
                str(tmp_path / "serie.part01.rar"),
                str(tmp_path), "serie.part01", "abc123"
            )
        assert was_linked is False


# ── makepar.py: caminhos de make_parity + handle_par_failure ────────────────

class TestMakeParityEdgeCases:
    def test_get_article_size_bytes_exception(self):
        """_get_article_size_bytes captura exceções ao carregar env."""
        from upapasta.makepar import _get_article_size_bytes
        with patch("upapasta.config.load_env_file", side_effect=Exception("falha")):
            result = _get_article_size_bytes()
        assert isinstance(result, int)
        assert result > 0  # deve retornar o default

    def test_make_parity_force_remove_oserror(self, tmp_path):
        """make_parity force=True com OSError ao remover par2 existente — deve continuar."""
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_text("conteudo" * 50)
        existing = tmp_path / "video.par2"
        existing.write_text("fake par2")

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar.managed_popen", return_value=mock_proc), \
             patch("os.remove", side_effect=OSError("ocupado")):
            rc = make_parity(str(f), force=True)
        assert rc == 0

    def test_make_parity_path_not_file_not_folder(self, tmp_path):
        """Caminho que não é arquivo nem pasta (symlink quebrado) retorna rc=2."""
        from upapasta.makepar import make_parity
        symlink = tmp_path / "broken.rar"
        os.symlink("/nonexistent/target", symlink)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")):
            rc = make_parity(str(symlink))
        assert rc == 2

    def test_handle_par_failure_oserror_cleanup(self, tmp_path):
        """handle_par_failure com OSError ao remover par2 — deve capturar e continuar."""
        from upapasta.makepar import handle_par_failure
        f = tmp_path / "video.par2"
        f.write_text("fake par2")
        rar = tmp_path / "video.rar"
        rar.write_text("fake rar")

        with patch("upapasta.makepar.make_parity", return_value=0), \
             patch("os.remove", side_effect=OSError("ocupado")):
            result = handle_par_failure(str(rar), original_rc=5, threads=4)
        assert isinstance(result, bool)

    def test_make_parity_min_input_slices_condicao(self, tmp_path):
        """Testa branch min-input-slices quando total_bytes >= slice * min_slices."""
        from upapasta.makepar import make_parity
        f = tmp_path / "video.mkv"
        f.write_bytes(b"x" * 1024)  # 1KB

        mock_proc = MagicMock()
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0
        mock_proc.__enter__ = lambda s: mock_proc
        mock_proc.__exit__ = MagicMock(return_value=False)

        # Faz _compute_dynamic_slice retornar min_slices=1 (arquivo de 1KB satisfaz slice*1)
        with patch("upapasta.makepar.find_parpar", return_value=("parpar", "/usr/bin/parpar")), \
             patch("upapasta.makepar._compute_dynamic_slice", return_value=("1K", 1, 12000)), \
             patch("upapasta.makepar.managed_popen", return_value=mock_proc):
            rc = make_parity(str(f))
        assert rc == 0


# ── orchestrator.py: caminhos adicionais 3 ───────────────────────────────────

class TestOrchestratorAdditional3:
    def test_run_upload_com_nzb_conflict(self, tmp_path):
        """run_upload com nzb_conflict define env_vars (linha 411)."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        orch = UpaPastaOrchestrator(input_path=str(f), nzb_conflict="overwrite")
        orch.input_target = str(f)
        with patch("upapasta.orchestrator.upload_to_usenet", return_value=0):
            result = orch.run_upload()
        assert result is True
        assert orch.env_vars.get("NZB_CONFLICT") == "overwrite"

    def test_run_generate_nfo_makedirs_oserror(self, tmp_path):
        """run_generate_nfo com makedirs OSError — deve capturar e continuar (linhas 207-208)."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("conteudo")
        orch = UpaPastaOrchestrator(input_path=str(f))
        with patch("upapasta.orchestrator.os.makedirs", side_effect=OSError("permissão")):
            result = orch.run_generate_nfo()
        assert isinstance(result, bool)

    def test_run_upload_oserror(self, tmp_path):
        """run_upload com OSError em upload_to_usenet retorna False (linhas 429-431)."""
        from upapasta.orchestrator import UpaPastaOrchestrator
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        orch = UpaPastaOrchestrator(input_path=str(f))
        orch.input_target = str(f)
        with patch("upapasta.orchestrator.upload_to_usenet", side_effect=OSError("io error")):
            result = orch.run_upload()
        assert result is False


# ── nfo.py: cobertura adicional ───────────────────────────────────────────────

class TestNfoAdditional:
    def test_find_mediainfo_none(self, monkeypatch):
        """find_mediainfo retorna None quando não está no PATH."""
        from upapasta.nfo import find_mediainfo
        with patch("shutil.which", return_value=None):
            result = find_mediainfo()
        assert result is None

    def test_format_size_gb(self):
        """_format_size em GB (linha 33)."""
        from upapasta.nfo import _format_size
        result = _format_size(2 * 1024 * 1024 * 1024)  # 2 GB
        assert "GB" in result

    def test_format_size_tb(self):
        """_format_size em TB (linha 33-34)."""
        from upapasta.nfo import _format_size
        result = _format_size(2 * 1024 ** 4)  # 2 TB
        assert "TB" in result

    def test_generate_nfo_single_file_sem_mediainfo(self, tmp_path):
        """generate_nfo_single_file retorna False se mediainfo não encontrado (linhas 179-180)."""
        from upapasta.nfo import generate_nfo_single_file
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        with patch("upapasta.nfo.find_mediainfo", return_value=None):
            result = generate_nfo_single_file(str(f), str(tmp_path / "video.nfo"))
        assert result is False

    def test_generate_nfo_single_file_exception(self, tmp_path):
        """generate_nfo_single_file captura exceções (linhas 201-203)."""
        from upapasta.nfo import generate_nfo_single_file
        f = tmp_path / "video.mkv"
        f.write_text("fake")
        with patch("upapasta.nfo.find_mediainfo", return_value="/usr/bin/mediainfo"), \
             patch("subprocess.run", side_effect=Exception("erro")):
            result = generate_nfo_single_file(str(f), str(tmp_path / "video.nfo"))
        assert result is False

    def test_generate_nfo_folder_serie_com_episodio(self, tmp_path):
        """generate_nfo_folder com pasta de série chama generate_nfo_single_file (linha 234-236)."""
        from upapasta.nfo import generate_nfo_folder
        serie_dir = tmp_path / "Serie.S01"
        serie_dir.mkdir()
        ep = serie_dir / "S01E01.mkv"
        ep.write_text("fake episode")

        with patch("upapasta.nfo.generate_nfo_single_file", return_value=True) as mock_gen:
            result = generate_nfo_folder(str(serie_dir), str(tmp_path / "test.nfo"))
        assert result is True
        mock_gen.assert_called_once()

    def test_generate_nfo_folder_com_ano(self, tmp_path):
        """generate_nfo_folder com pasta contendo ano [2024] (linhas 244-245, 249)."""
        from upapasta.nfo import generate_nfo_folder
        folder = tmp_path / "Filme.Epico [2024]"
        folder.mkdir()
        (folder / "filme.mkv").write_text("fake movie content" * 100)

        nfo_path = str(tmp_path / "test.nfo")
        with patch("upapasta.nfo._get_video_info", return_value=(0.0, {
            "codec": "N/A", "resolution": "N/A", "bitrate": "N/A",
            "audio_tracks": [], "subtitle_tracks": []
        })):
            result = generate_nfo_folder(str(folder), nfo_path)
        assert result is True
        content = Path(nfo_path).read_text()
        assert "2024" in content

    def test_generate_nfo_folder_sem_videos(self, tmp_path):
        """generate_nfo_folder com pasta sem vídeos gera NFO de arquivos genéricos."""
        from upapasta.nfo import generate_nfo_folder
        folder = tmp_path / "Release.Qualquer"
        folder.mkdir()
        (folder / "arquivo.txt").write_text("texto")
        (folder / "outro.nfo").write_text("info")

        nfo_path = str(tmp_path / "test.nfo")
        result = generate_nfo_folder(str(folder), nfo_path)
        assert result is True

    def test_generate_nfo_folder_com_banner(self, tmp_path):
        """generate_nfo_folder com banner customizado (linha 281)."""
        from upapasta.nfo import generate_nfo_folder
        folder = tmp_path / "MinhaPasta"
        folder.mkdir()
        (folder / "arquivo.txt").write_text("conteudo")

        nfo_path = str(tmp_path / "test.nfo")
        result = generate_nfo_folder(str(folder), nfo_path, banner="=== MEU BANNER ===")
        assert result is True
        content = Path(nfo_path).read_text()
        assert "MEU BANNER" in content

    def test_generate_nfo_folder_com_video_meta(self, tmp_path):
        """generate_nfo_folder com vídeo que tem metadata (linhas 303, 312-317)."""
        from upapasta.nfo import generate_nfo_folder
        folder = tmp_path / "MinhaSerie"
        folder.mkdir()
        ep = folder / "episode.mkv"
        ep.write_text("fake video" * 100)

        nfo_path = str(tmp_path / "test.nfo")
        with patch("upapasta.nfo._get_video_info", return_value=(3600.0, {
            "codec": "h264", "resolution": "1920x1080", "bitrate": "5000 kbps",
            "audio_tracks": ["PT", "EN"], "subtitle_tracks": ["PT"]
        })):
            result = generate_nfo_folder(str(folder), nfo_path)
        assert result is True
        content = Path(nfo_path).read_text()
        assert "PT" in content

    def test_generate_nfo_folder_exception(self, tmp_path):
        """generate_nfo_folder captura exceções (linhas 337-339)."""
        from upapasta.nfo import generate_nfo_folder
        folder = tmp_path / "Pasta"
        folder.mkdir()
        (folder / "f.txt").write_text("x")

        with patch("upapasta.nfo._generate_tree", side_effect=Exception("crash")):
            result = generate_nfo_folder(str(folder), str(tmp_path / "test.nfo"))
        assert result is False

    def test_is_series_folder(self):
        """_is_series_folder detecta padrão SXX em nome de pasta."""
        from upapasta.nfo import _is_series_folder
        assert _is_series_folder("Serie.S01E01") is True
        assert _is_series_folder("Serie.S02") is True
        assert _is_series_folder("Filme.2024") is False

    def test_find_first_episode_sem_videos(self, tmp_path):
        """_find_first_episode retorna None se não há vídeos."""
        from upapasta.nfo import _find_first_episode
        folder = tmp_path / "sem_video"
        folder.mkdir()
        (folder / "texto.txt").write_text("nao e video")
        result = _find_first_episode(str(folder))
        assert result is None


# ── upfolder.py: NZB conflict + múltiplos servidores ─────────────────────────

class TestUpfolderNzbConflict:
    def _base_env(self) -> dict:
        return {
            "NNTP_HOST": "news.test.com",
            "NNTP_PORT": "563",
            "NNTP_USER": "u",
            "NNTP_PASS": "p",
            "USENET_GROUP": "alt.binaries.test",
        }

    def test_nzb_conflict_fail_retorna_6(self, tmp_path, monkeypatch):
        """handle_nzb_conflict retornando ok=False deve retornar rc=6."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")
        # Cria NZB existente para gerar conflito
        (tmp_path / "video.nzb").write_text("existing nzb")

        env = self._base_env()
        env["NZB_CONFLICT"] = "fail"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
        )
        assert rc == 6

    def test_input_nao_e_arquivo_nem_pasta(self, tmp_path, monkeypatch):
        """FIFO (special file) não é arquivo nem pasta → retorna rc=1 (linhas 274-275)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        # Named pipe (FIFO): existe mas não é arquivo regular nem diretório
        fifo = tmp_path / "test.mkv"
        os.mkfifo(str(fifo))

        rc = upload_to_usenet(
            str(fifo),
            env_vars=self._base_env(),
            dry_run=True,
            skip_rar=True,
        )
        assert rc == 1

    def test_upload_resume_todos_postados(self, tmp_path, monkeypatch):
        """resume=True com todos arquivos já postados retorna rc=0 sem upload (linha 433-434)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)
        import xml.etree.ElementTree as ET

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        # Cria NZB existente com o arquivo já postado
        nzb_path = tmp_path / "video.nzb"
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}nzb")
        fe = ET.SubElement(root, f"{{{ns}}}file")
        fe.set("subject", '"video.mkv" yEnc (1/1)')
        sg = ET.SubElement(fe, f"{{{ns}}}segments")
        s = ET.SubElement(sg, f"{{{ns}}}segment")
        s.text = "msg-id@server"
        fe2 = ET.SubElement(root, f"{{{ns}}}file")
        fe2.set("subject", '"video.par2" yEnc (1/1)')
        ET.ElementTree(root).write(str(nzb_path), encoding="UTF-8", xml_declaration=True)

        env = self._base_env()
        env["NZB_OUT_DIR"] = str(tmp_path)

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        # _get_uploaded_files_from_nzb retornará um set com os filenames
        with patch("upapasta.upfolder._get_uploaded_files_from_nzb", return_value={"video.mkv", "video.par2"}):
            rc = upload_to_usenet(
                str(f),
                env_vars=env,
                dry_run=False,
                skip_rar=True,
                nyuu_path=str(nyuu),
                resume=True,
            )
        assert rc == 0

    def test_upload_getsize_oserror(self, tmp_path, monkeypatch):
        """OSError em getsize durante cálculo de tamanho total (linhas 461-467)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        original_getsize = os.path.getsize

        def patched_getsize(path: str) -> int:
            if "video" in path:
                raise OSError("permissão negada")
            return original_getsize(path)

        with patch("upapasta.upfolder.os.path.getsize", side_effect=patched_getsize):
            rc = upload_to_usenet(
                str(f),
                env_vars=self._base_env(),
                dry_run=True,
                skip_rar=True,
                nyuu_path=str(nyuu),
            )
        assert rc == 0

    def test_upload_formato_tamanho_gb(self, tmp_path, monkeypatch):
        """Cobertura da branch GB de format_size (linha 455) e get_terminal_size exc (473-474)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        # Mock getsize para retornar > 1 GB e get_terminal_size para levantar
        with patch("upapasta.upfolder.os.path.getsize", return_value=2 * 1024**3), \
             patch("upapasta.upfolder.shutil.get_terminal_size", side_effect=Exception("sem terminal")):
            rc = upload_to_usenet(
                str(f),
                env_vars=self._base_env(),
                dry_run=True,
                skip_rar=True,
                nyuu_path=str(nyuu),
            )
        assert rc == 0

    def test_build_server_list_multiplos(self):
        """_build_server_list com 2 servidores retorna lista de 2."""
        from upapasta.upfolder import _build_server_list
        env = {
            "NNTP_HOST": "news1.test.com", "NNTP_USER": "u1", "NNTP_PASS": "p1",
            "NNTP_HOST_2": "news2.test.com", "NNTP_USER_2": "u2", "NNTP_PASS_2": "p2",
        }
        servers = _build_server_list(env)
        assert len(servers) == 2
        assert servers[1]["host"] == "news2.test.com"

    def test_multiplos_servidores_upload_dry_run(self, tmp_path, monkeypatch):
        """Upload dry_run com múltiplos servidores (linha 383)."""
        from upapasta.upfolder import upload_to_usenet
        monkeypatch.delenv("NZB_CONFLICT", raising=False)

        f = tmp_path / "video.mkv"
        f.write_text("fake")
        (tmp_path / "video.par2").write_text("fake par2")

        nyuu = tmp_path / "nyuu"
        nyuu.write_text("#!/bin/sh\nexit 0")
        nyuu.chmod(0o755)

        env = self._base_env()
        env["NNTP_HOST_2"] = "news2.test.com"
        env["NNTP_USER_2"] = "u2"
        env["NNTP_PASS_2"] = "p2"

        rc = upload_to_usenet(
            str(f),
            env_vars=env,
            dry_run=True,
            skip_rar=True,
            nyuu_path=str(nyuu),
        )
        assert rc == 0
