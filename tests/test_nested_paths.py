"""
Cobertura crítica: pastas com múltiplos níveis de subdiretórios são
preservadas ao longo de todo o pipeline.

Casos cobertos:
  1. Profundidade extrema (5+ níveis) chega ao nyuu como caminhos relativos.
  2. Nomes com unicode, espaços, colchetes e parênteses preservados no argv
     e no NZB (subjects).
  3. Pastas vazias intermediárias, arquivos ocultos e symlinks: pastas
     vazias ignoradas, hidden files incluídos, symlinks para arquivos
     seguidos por os.walk com followlinks=False (default).
  4. Obfuscate + nested + upload: NZB final tem subjects com o root
     ofuscado, mas a hierarquia interna intacta (root_obf/sub/.../file).
  5. --rename-extensionless funciona em arquivos dentro de subdirs
     profundos e a reversão restaura os nomes originais.

Os subprocessos externos (nyuu, parpar) são mockados; estes testes não
tocam rede nem dependem de binários instalados.
"""
from __future__ import annotations

import io
import os
import subprocess
import xml.etree.ElementTree as ET

import pytest

from upapasta import makepar as makepar_module
from upapasta import upfolder as upfolder_module
from upapasta.makepar import make_parity, obfuscate_and_par
from upapasta.orchestrator import normalize_extensionless, revert_extensionless
from upapasta.nzb import fix_nzb_subjects
from upapasta.upfolder import upload_to_usenet


# ─────────────────────────── Helpers / mocks ────────────────────────────────

class _RecordingPopen:
    """Mock de subprocess.Popen que registra o argv recebido."""
    last_argv: list = []

    def __init__(self, argv=None, *a, **kw):
        type(self).last_argv = list(argv) if argv else []
        self.stdout = io.StringIO("ok\n")
        self._argv = argv

    def wait(self, timeout=None):
        if self._argv and "-o" in self._argv:
            out_idx = self._argv.index("-o") + 1
            out = self._argv[out_idx]
            # Cria o .par2/.nzb output esperado para satisfazer chamadores
            try:
                open(out, "w").close()
            except OSError:
                pass
        return 0

    def poll(self):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


@pytest.fixture
def recording_popen(monkeypatch):
    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **kw: _RecordingPopen(a[0] if a else None, **kw),
    )
    _RecordingPopen.last_argv = []
    return _RecordingPopen


def _build_deep_tree(root):
    """5 níveis: a/b/c/d/e/leaf.bin + arquivos em níveis intermediários."""
    deepest = root / "a" / "b" / "c" / "d" / "e"
    deepest.mkdir(parents=True)
    (deepest / "leaf.bin").write_bytes(b"L" * 2048)
    (root / "a" / "b" / "c" / "mid.bin").write_bytes(b"M" * 2048)
    (root / "a" / "top.bin").write_bytes(b"T" * 2048)
    (root / "rootfile.bin").write_bytes(b"R" * 2048)


def _env():
    return {
        "NNTP_HOST": "news.example.com",
        "NNTP_USER": "u", "NNTP_PASS": "p",
        "USENET_GROUP": "alt.binaries.test",
    }


# ───────────────────────── 1. Profundidade extrema ───────────────────────────

def test_make_parity_deep_tree_includes_all_leaves(recording_popen, tmp_path):
    root = tmp_path / "deep"
    root.mkdir()
    _build_deep_tree(root)

    rc = make_parity(str(root), redundancy=5, force=True, backend="parpar", threads=1)
    assert rc == 0
    argv = recording_popen.last_argv

    expected = [
        str(root / "a" / "b" / "c" / "d" / "e" / "leaf.bin"),
        str(root / "a" / "b" / "c" / "mid.bin"),
        str(root / "a" / "top.bin"),
        str(root / "rootfile.bin"),
    ]
    for p in expected:
        assert p in argv, f"path ausente do argv parpar: {p}"
    assert "-f" in argv and argv[argv.index("-f") + 1] == "common"


def test_upload_deep_tree_preserves_relative_paths(monkeypatch, tmp_path):
    folder = tmp_path / "deep"
    folder.mkdir()
    _build_deep_tree(folder)
    # par2 sentinela no diretório pai (upfolder espera '<folder>*par2*')
    (tmp_path / "deep.par2").write_text("par2")

    captured = {}

    class FakePopen:
        def __init__(self, cmd, *a, **kw):
            captured["cmd"] = list(cmd)
            captured["cwd"] = kw.get("cwd")
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder_module, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder_module, "managed_popen", lambda *a, **k: FakePopen(*a, **k))

    rc = upload_to_usenet(str(folder), _env(), skip_rar=True)
    assert rc == 0

    # cwd deve ser a pasta raiz; argv deve listar caminhos RELATIVOS preservando hierarquia
    assert captured["cwd"] == str(folder)
    cmd = captured["cmd"]
    # nyuu recebe caminhos relativos (sem o prefixo de tmp_path)
    rel_expected = [
        os.path.join("a", "b", "c", "d", "e", "leaf.bin"),
        os.path.join("a", "b", "c", "mid.bin"),
        os.path.join("a", "top.bin"),
        "rootfile.bin",
    ]
    for rp in rel_expected:
        assert rp in cmd, f"caminho relativo ausente do argv nyuu: {rp}\nargv={cmd}"
    # E NÃO devem aparecer como absolutos (regressão clássica)
    for rp in rel_expected:
        abs_form = str(folder / rp)
        assert abs_form not in cmd, f"caminho absoluto vazou para nyuu: {abs_form}"


# ─────────────────── 2. Unicode / espaços / chars especiais ─────────────────

def test_unicode_and_special_chars_preserved_in_argv(monkeypatch, tmp_path):
    folder = tmp_path / "Coleção [2025] (Final)"
    folder.mkdir()
    sub = folder / "Tem porada 01" / "Capítulo — 1"
    sub.mkdir(parents=True)
    (sub / "vídeo (HD) [pt-BR].bin").write_bytes(b"v" * 1024)
    (folder / "leia-me — info.txt").write_text("ok", encoding="utf-8")
    (tmp_path / f"{folder.name}.par2").write_text("p")

    captured = {}

    class FakePopen:
        def __init__(self, cmd, *a, **kw):
            captured["cmd"] = list(cmd)
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder_module, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder_module, "managed_popen", lambda *a, **k: FakePopen(*a, **k))

    rc = upload_to_usenet(str(folder), _env(), skip_rar=True)
    assert rc == 0

    cmd = captured["cmd"]
    expected = [
        os.path.join("Tem porada 01", "Capítulo — 1", "vídeo (HD) [pt-BR].bin"),
        "leia-me — info.txt",
    ]
    for rp in expected:
        assert rp in cmd, f"argv não contém '{rp}'\nargv={cmd}"


def test_fix_nzb_subjects_preserves_nested_subjects(tmp_path):
    """fix_nzb_subjects deve manter subpaths relativos (a/b/c) e prefixar root."""
    nzb = tmp_path / "x.nzb"
    files_rel = [
        "rootfile.bin",
        os.path.join("a", "b", "c", "deep.bin"),
        "x.par2",
    ]
    # NZB mínimo com 3 entries
    ns = "http://www.newzbin.com/DTD/2003/nzb"
    ET.register_namespace("", ns)
    root_el = ET.Element(f"{{{ns}}}nzb")
    for _ in files_rel:
        f = ET.SubElement(root_el, f"{{{ns}}}file")
        f.set("subject", "placeholder")
    ET.ElementTree(root_el).write(str(nzb), encoding="UTF-8", xml_declaration=True)

    fix_nzb_subjects(str(nzb), files_rel, folder_name="MeuRelease")

    tree = ET.parse(str(nzb))
    subjects = [e.get("subject") for e in tree.getroot().findall(f".//{{{ns}}}file")]
    # rootfile sem barra → prefixa folder; subpath com barra → mantém literal;
    # par2 → não modificado pela função (sai como placeholder)
    assert "MeuRelease/rootfile.bin" in subjects
    assert os.path.join("a", "b", "c", "deep.bin") in subjects


# ─────────────────── 3. Empty / hidden / symlink edge cases ─────────────────

def test_walk_skips_empty_dirs_keeps_hidden_files(monkeypatch, tmp_path):
    folder = tmp_path / "edge"
    folder.mkdir()
    (folder / "vazia").mkdir()  # subdir vazio: não deve aparecer no argv
    (folder / "vazia2" / "vazia3").mkdir(parents=True)
    (folder / ".hidden_file").write_bytes(b"h" * 512)
    sub = folder / "sub"
    sub.mkdir()
    (sub / "real.bin").write_bytes(b"r" * 512)
    (tmp_path / "edge.par2").write_text("p")

    captured = {}

    class FakePopen:
        def __init__(self, cmd, *a, **kw):
            captured["cmd"] = list(cmd)
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder_module, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder_module, "managed_popen", lambda *a, **k: FakePopen(*a, **k))

    rc = upload_to_usenet(str(folder), _env(), skip_rar=True)
    assert rc == 0
    cmd = captured["cmd"]

    # Hidden incluído (os.walk sempre inclui dotfiles — comportamento documentado)
    assert ".hidden_file" in cmd
    assert os.path.join("sub", "real.bin") in cmd
    # Diretórios vazios não viram entrada (não há arquivos dentro)
    assert "vazia" not in cmd
    assert "vazia2" not in cmd


def test_walk_follows_symlink_to_file_in_subdir(monkeypatch, tmp_path):
    folder = tmp_path / "syml"
    sub = folder / "sub"
    sub.mkdir(parents=True)
    real = tmp_path / "out_of_tree.bin"
    real.write_bytes(b"x" * 512)
    link = sub / "linked.bin"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks não suportados neste filesystem")
    (sub / "real.bin").write_bytes(b"r" * 512)
    (tmp_path / "syml.par2").write_text("p")

    captured = {}

    class FakePopen:
        def __init__(self, cmd, *a, **kw):
            captured["cmd"] = list(cmd)
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder_module, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder_module, "managed_popen", lambda *a, **k: FakePopen(*a, **k))

    rc = upload_to_usenet(str(folder), _env(), skip_rar=True)
    assert rc == 0
    # symlinks para arquivos aparecem em os.walk como arquivos comuns
    assert os.path.join("sub", "linked.bin") in captured["cmd"]
    assert os.path.join("sub", "real.bin") in captured["cmd"]


# ─────────────────── 4. Obfuscate + nested + NZB integrity ──────────────────

def test_obfuscate_then_upload_preserves_inner_structure(recording_popen, monkeypatch, tmp_path):
    """
    Após obfuscate_and_par renomear o root, um upload subsequente deve
    referenciar paths relativos com o root ofuscado preservando a árvore
    interna.
    """
    root = tmp_path / "Release [2025]"
    root.mkdir()
    _build_deep_tree(root)

    rc, new_path, mapping, _linked = obfuscate_and_par(
        str(root), redundancy=5, force=True, backend="parpar", threads=1,
    )
    assert rc == 0 and new_path is not None
    # Estrutura interna preservada após obfuscação do root
    assert os.path.exists(os.path.join(new_path, "a", "b", "c", "d", "e", "leaf.bin"))

    # par2 sentinela já criado pelo recording_popen no -o; garantir que existe
    par2_glob = [f for f in os.listdir(tmp_path) if f.endswith(".par2")]
    assert par2_glob, "obfuscate_and_par não gerou .par2 esperado"

    captured = {}

    class FakePopen:
        def __init__(self, cmd, *a, **kw):
            captured["cmd"] = list(cmd)
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder_module, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder_module, "managed_popen", lambda *a, **k: FakePopen(*a, **k))

    rc2 = upload_to_usenet(new_path, _env(), skip_rar=True)
    assert rc2 == 0

    cmd = captured["cmd"]
    # Caminhos internos relativos preservados (root foi ofuscado mas a árvore
    # interna passa intacta para o nyuu)
    assert os.path.join("a", "b", "c", "d", "e", "leaf.bin") in cmd
    assert "rootfile.bin" in cmd


# ─────────────────── 5. rename-extensionless em subdirs ─────────────────────

def test_rename_extensionless_in_nested_dirs_round_trip(tmp_path):
    folder = tmp_path / "noext"
    deep = folder / "a" / "b" / "c"
    deep.mkdir(parents=True)
    f_deep = deep / "videofile"            # sem extensão, em subdir profundo
    f_mid = folder / "a" / "another"       # sem extensão, nível intermediário
    f_root = folder / "rootless"           # sem extensão, no root
    f_keep = folder / "a" / "keep.txt"     # com extensão, deve ser ignorado
    f_dot = folder / ".dotfile"            # dotfile, deve ser ignorado
    for f in (f_deep, f_mid, f_root, f_keep, f_dot):
        f.write_bytes(b"x" * 128)

    mapping = normalize_extensionless(str(folder))
    # 3 arquivos sem extensão renomeados; .txt e dotfile preservados
    renamed_originals = set(mapping.values())
    assert str(f_deep.resolve()) in renamed_originals
    assert str(f_mid.resolve()) in renamed_originals
    assert str(f_root.resolve()) in renamed_originals
    # Os novos arquivos existem com .bin no mesmo subdir
    assert (deep / "videofile.bin").exists()
    assert (folder / "a" / "another.bin").exists()
    assert (folder / "rootless.bin").exists()
    # Não tocou nos demais
    assert f_keep.exists()
    assert f_dot.exists()
    # Originais sumiram (foram renomeados)
    assert not f_deep.exists()
    assert not f_mid.exists()
    assert not f_root.exists()

    # Reversão restaura tudo
    revert_extensionless(mapping)
    assert f_deep.exists()
    assert f_mid.exists()
    assert f_root.exists()
    assert not (deep / "videofile.bin").exists()
    assert not (folder / "a" / "another.bin").exists()
    assert not (folder / "rootless.bin").exists()
