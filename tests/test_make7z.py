import os
import shutil
from unittest.mock import patch

import pytest

from upapasta.make7z import _volume_size_bytes, find_7z, make_7z


def test_find_7z():
    with patch("shutil.which", return_value="/usr/bin/7z"):
        assert find_7z() == "/usr/bin/7z"


def test_volume_size_bytes():
    # Abaixo de 10GB -> None
    assert _volume_size_bytes(5 * 1024**3) is None
    # 20GB -> deve dividir por 100 e arredondar para cima de 5MB
    # 20GB / 100 = 200MB. Arredondado para 1GB (mínimo)
    # 1024^3 = 1073741824. Arredondado para cima de 5MB -> 1074790400
    assert _volume_size_bytes(20 * 1024**3) == 1074790400


class TestMake7z:
    def test_input_nao_existe(self, tmp_path):
        rc, path = make_7z(str(tmp_path / "ghost"))
        assert rc == 2
        assert path is None

    def test_arquivo_ja_existe(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        archive = tmp_path / "data.7z"
        archive.write_text("dummy")

        rc, path = make_7z(str(folder), force=False)
        assert rc == 3

    @pytest.mark.skipif(shutil.which("7z") is None, reason="7z não instalado")
    def test_make_7z_success_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")

        rc, path = make_7z(str(f))
        assert rc == 0
        assert path is not None
        assert path.endswith(".7z")
        assert os.path.exists(path)

    @pytest.mark.skipif(shutil.which("7z") is None, reason="7z não instalado")
    def test_make_7z_success_folder(self, tmp_path):
        folder = tmp_path / "mypasta"
        folder.mkdir()
        (folder / "file.txt").write_text("content")

        rc, path = make_7z(str(folder))
        assert rc == 0
        assert path is not None
        assert path.endswith(".7z")
        assert os.path.exists(path)

    @pytest.mark.skipif(shutil.which("7z") is None, reason="7z não instalado")
    def test_make_7z_with_password(self, tmp_path):
        f = tmp_path / "secret.txt"
        f.write_text("top secret")

        rc, path = make_7z(str(f), password="123")
        assert rc == 0
        assert os.path.exists(path)

    @pytest.mark.skipif(shutil.which("7z") is None, reason="7z não instalado")
    def test_make_7z_volumes(self, tmp_path):
        folder = tmp_path / "big_data"
        folder.mkdir()
        # Cria arquivo grande o suficiente para disparar volumes
        with patch("upapasta.make7z._MIN_SPLIT_SIZE", 1024 * 1024):
            with patch("upapasta.make7z._MIN_VOLUME_SIZE", 512 * 1024):
                # 6 MB para garantir que ultrapassa o volume (que será arredondado para 5MB)
                (folder / "big.bin").write_bytes(b"x" * (6 * 1024 * 1024))

                rc, path = make_7z(str(folder))
                assert rc == 0
                assert path is not None
                assert path.endswith(".7z.001")
                assert os.path.exists(path)
                assert os.path.exists(path.replace(".001", ".002"))

        # Verifica se está encriptado (7z l -p... deve funcionar, sem -p deve falhar ou pedir)
        # Mas basta o rc=0 para o teste de integração
