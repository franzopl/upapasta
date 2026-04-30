"""
Smoke test opcional: se parpar real estiver no PATH, gera PAR2 de uma
arvore aninhada e confere que os paths internos foram preservados nos .par2
(via parpar -i, que imprime info do recovery set).

Skip se parpar ausente.
"""
import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("parpar") is None,
    reason="parpar nao encontrado no PATH",
)


def test_parpar_preserves_subdirs_in_par2(tmp_path):
    root = tmp_path / "release"
    (root / "season1" / "ep01").mkdir(parents=True)
    (root / "season1" / "ep01" / "video.bin").write_bytes(b"x" * 4096)
    (root / "season1" / "extras.bin").write_bytes(b"e" * 4096)
    (root / "readme.bin").write_bytes(b"r" * 4096)

    out_par2 = root.parent / "release.par2"
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            files.append(os.path.join(dp, f))

    rc = subprocess.run(
        [
            "parpar", "-s", "1M", "--min-input-slices=1",
            "-r", "5%", "-f", "common", "-o", str(out_par2),
        ] + files,
        capture_output=True, text=True, timeout=60,
    )
    assert rc.returncode == 0, rc.stderr
    assert out_par2.exists()

    # PAR2 grava filenames em UTF-8 plaintext nos pacotes FileDesc.
    # Procuramos os subdirs diretamente no conteudo binario do .par2.
    blob = out_par2.read_bytes()
    assert b"season1" in blob
    assert b"ep01" in blob
    assert b"video.bin" in blob
