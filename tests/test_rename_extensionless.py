"""
--rename-extensionless: arquivos sem extensão são renomeados para .bin antes
do upload, e o mapa permite reversão em caso de falha.

Os helpers vivem em upapasta.orchestrator (a serem implementados na fase 3):
  - normalize_extensionless(root) -> dict[novo_path, original_path]
  - revert_extensionless(mapping) -> None
"""
import pytest

orchestrator = pytest.importorskip("upapasta.orchestrator")
if not hasattr(orchestrator, "normalize_extensionless"):
    pytest.skip(
        "helpers normalize_extensionless/revert_extensionless ainda não implementados",
        allow_module_level=True,
    )
normalize_extensionless = orchestrator.normalize_extensionless
revert_extensionless = orchestrator.revert_extensionless


def _mktree(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "README").write_text("x")
    (root / "data").write_bytes(b"y")
    (root / "video.mkv").write_bytes(b"z")
    sub = root / "sub"
    sub.mkdir()
    (sub / "INDEX").write_text("idx")


def test_renames_extensionless_files_to_bin(tmp_path):
    root = tmp_path / "tree"
    _mktree(root)

    mapping = normalize_extensionless(str(root))

    assert (root / "README.bin").exists() and not (root / "README").exists()
    assert (root / "data.bin").exists() and not (root / "data").exists()
    assert (root / "video.mkv").exists()  # com extensão: intacto
    assert (root / "sub" / "INDEX.bin").exists()

    # Mapa: novo → original
    assert str(root / "README.bin") in mapping
    assert mapping[str(root / "README.bin")] == str(root / "README")


def test_reverts_on_demand(tmp_path):
    root = tmp_path / "tree"
    _mktree(root)
    mapping = normalize_extensionless(str(root))
    revert_extensionless(mapping)
    assert (root / "README").exists() and not (root / "README.bin").exists()
    assert (root / "data").exists()
    assert (root / "sub" / "INDEX").exists()


def test_idempotent_on_already_extensioned(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_text("x")
    (root / "b.mkv").write_text("y")
    mapping = normalize_extensionless(str(root))
    assert mapping == {}
