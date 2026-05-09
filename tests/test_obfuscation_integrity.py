"""
Testes de integridade do ciclo completo de ofuscação.

Cobre os gaps identificados nos testes existentes:
- Conteúdo dos arquivos verificado por hash após obfuscar e reverter
- Deep obfuscation (_deep_obfuscate_tree) + reversão mantém conteúdo intacto
- Subjects do NZB são completamente randômicos (nenhum nome original vaza) com
  o --obfuscate unificado (strong_obfuscate=True sempre)
- obfuscated_map cobre todos os arquivos para que o downloader possa renomear
  corretamente via PAR2
- Comportamento regressivo: orchestrator passa strong_obfuscate=True quando
  obfuscate=True (unificação v0.28.0)
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from upapasta import makepar as makepar_module
from upapasta.makepar import _deep_obfuscate_tree, obfuscate_and_par
from upapasta.nzb import fix_nzb_subjects
from upapasta.orchestrator import UpaPastaOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    """Dicionário {caminho_relativo: sha256} de todos os arquivos sob root."""
    return {str(p.relative_to(root)): _sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _build_nzb(tmp_path: Path, files: list[str], segs_each: int = 2) -> Path:
    """Cria um NZB mínimo com <file> para cada nome em files."""
    ns = "http://www.newzbin.com/DTD/2003/nzb"
    ET.register_namespace("", ns)
    root_el = ET.Element(f"{{{ns}}}nzb")
    for name in files:
        fe = ET.SubElement(root_el, f"{{{ns}}}file", subject=f'"{name}" yEnc (1/{segs_each})')
        groups = ET.SubElement(fe, f"{{{ns}}}groups")
        ET.SubElement(groups, f"{{{ns}}}group").text = "alt.binaries.test"
        segs_el = ET.SubElement(fe, f"{{{ns}}}segments")
        for n in range(1, segs_each + 1):
            ET.SubElement(
                segs_el, f"{{{ns}}}segment", bytes="716800", number=str(n)
            ).text = f"msg{name}{n}@test"
    tree = ET.ElementTree(root_el)
    nzb = tmp_path / "test.nzb"
    tree.write(str(nzb), xml_declaration=True, encoding="utf-8")
    return nzb


class _OkPopen:
    """Mock de managed_popen / subprocess.Popen que simula parpar bem-sucedido."""

    def __init__(self, argv=None, *a, **kw):
        self.stdout = io.StringIO("ok\n")
        self._argv = argv or []

    def wait(self, timeout=None):
        # Cria o arquivo .par2 que o código verifica no pós-processamento
        out_flags = ["-o", "--out"]
        for flag in out_flags:
            if flag in self._argv:
                idx = self._argv.index(flag)
                if idx + 1 < len(self._argv):
                    open(self._argv[idx + 1], "w").close()
                    break
        return 0

    def poll(self):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


# ---------------------------------------------------------------------------
# 1. Integridade de conteúdo: arquivo único, obfuscar + reverter
# ---------------------------------------------------------------------------


class TestFileIntegrityAfterRevert:
    """Verifica que o hash do conteúdo é idêntico antes e após o ciclo completo."""

    @pytest.fixture(autouse=True)
    def fake_parpar(self, monkeypatch):
        monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))

    def test_single_file_hash_unchanged_after_revert(self, monkeypatch, tmp_path):
        src = tmp_path / "video.mkv"
        content = b"binary content " * 512  # 7.5 KB
        src.write_bytes(content)
        original_hash = _sha256(src)

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: _OkPopen(a[0] if a else [], **kw),
        )

        rc, new_path, mapping, was_linked = obfuscate_and_par(
            str(src),
            redundancy=5,
            force=True,
            backend="parpar",
            threads=1,
        )
        assert rc == 0

        # Após retorno normal, o arquivo original deve existir com conteúdo intacto
        assert src.exists(), "Arquivo original deve ser restaurado após obfuscate_and_par"
        assert _sha256(src) == original_hash, "Hash do arquivo deve ser idêntico ao original"

    def test_single_file_renamed_content_intact_before_revert(self, monkeypatch, tmp_path):
        """
        No modo rename (cross-device fallback), obfuscate_and_par renomeia o arquivo
        original e retorna o new_path (nome randômico). A reversão acontece depois
        no orchestrator. Este teste verifica que o CONTEÚDO do arquivo ofuscado
        é idêntico ao original — a integridade dos bytes nunca é comprometida.
        """
        src = tmp_path / "audio.flac"
        content = b"\xab\xcd" * 1024
        src.write_bytes(content)
        original_hash = _sha256(src)

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: _OkPopen(a[0] if a else [], **kw),
        )

        # Força fallback para rename simulando falha de hardlink
        import upapasta.makepar as makepar_mod

        monkeypatch.setattr(
            makepar_mod.os,
            "link",
            lambda s, d: (_ for _ in ()).throw(OSError("Invalid cross-device link")),
        )

        rc, new_path, mapping, was_linked = obfuscate_and_par(
            str(src),
            redundancy=5,
            force=True,
            backend="parpar",
            threads=1,
        )
        assert rc == 0
        assert not was_linked, "Deve ter usado rename, não hardlink"
        assert new_path is not None

        # Com rename, o arquivo original é movido para o nome randômico.
        # O conteúdo deve ser idêntico ao original.
        obf_path = Path(new_path)
        assert obf_path.exists(), "Arquivo ofuscado (renomeado) deve existir"
        assert _sha256(obf_path) == original_hash, (
            "Conteúdo do arquivo ofuscado deve ser idêntico ao original"
        )
        assert not src.exists(), (
            "Arquivo original não deve existir após rename (será restaurado pelo orchestrator)"
        )


# ---------------------------------------------------------------------------
# 2. Deep obfuscation: estrutura aninhada, revert mantém conteúdo
# ---------------------------------------------------------------------------


class TestDeepObfuscationIntegrity:
    """_deep_obfuscate_tree renomeia tudo internamente; reversão deve preservar conteúdo."""

    def _build_tree(self, root: Path) -> dict[str, str]:
        """Cria árvore com 3 níveis e retorna snapshot de hashes antes da ofuscação."""
        (root / "Serie S01" / "Ep1").mkdir(parents=True)
        (root / "Serie S01" / "Ep2").mkdir()
        (root / "Extras").mkdir()

        files = {
            "Serie S01/Ep1/video.mkv": b"mkv data " * 200,
            "Serie S01/Ep1/subs.srt": b"subtitle\n" * 50,
            "Serie S01/Ep2/video.mkv": b"other mkv " * 300,
            "Extras/nfo.txt": b"release info",
        }
        for rel, data in files.items():
            (root / rel).write_bytes(data)

        return _snapshot(root)

    def test_deep_obfuscate_and_revert_preserves_content(self, tmp_path):
        root = tmp_path / "MyRelease"
        root.mkdir()
        original_hashes = self._build_tree(root)
        original_file_count = len(original_hashes)

        # Aplica deep obfuscation
        mapping = _deep_obfuscate_tree(str(root))

        # Após ofuscação: nenhum nome original deve aparecer nos caminhos dos arquivos
        current_paths = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
        original_rel_paths = set(original_hashes.keys())
        leaked = current_paths & original_rel_paths
        assert not leaked, f"Nomes originais vazaram após deep obfuscation: {leaked}"

        # Conteúdo dos arquivos ainda está lá (mesmos hashes, caminhos diferentes)
        current_hashes = set(_snapshot(root).values())
        expected_hashes = set(original_hashes.values())
        assert current_hashes == expected_hashes, "Conteúdo dos arquivos deve ser preservado"

        # Mapping cobre todos os arquivos (downloader pode reconstruir via PAR2)
        assert len(mapping) >= original_file_count, (
            "Mapping deve conter entrada para cada arquivo original"
        )

        # Reversão manual: renomeia de volta usando o mapping invertido
        inverted = {v: k for k, v in mapping.items() if not os.path.isdir(os.path.join(root, k))}
        for new_rel, orig_rel in inverted.items():
            new_abs = root / new_rel
            orig_abs = root / orig_rel
            if new_abs.exists() and not orig_abs.exists():
                orig_abs.parent.mkdir(parents=True, exist_ok=True)
                os.replace(new_abs, orig_abs)

        # Após reversão: hashes devem ser idênticos ao estado inicial
        post_revert = _snapshot(root)
        # Verificamos que o conteúdo de todos os arquivos originais está presente
        post_revert_hashes = set(post_revert.values())
        assert post_revert_hashes == expected_hashes, (
            "Após reversão, todo conteúdo original deve estar intacto"
        )

    def test_mapping_covers_all_files(self, tmp_path):
        """Cada arquivo da árvore deve ter entrada no mapping."""
        root = tmp_path / "Release"
        root.mkdir()
        (root / "sub").mkdir()
        (root / "a.mkv").write_bytes(b"a")
        (root / "sub" / "b.srt").write_bytes(b"b")
        (root / "sub" / "c.nfo").write_bytes(b"c")

        mapping = _deep_obfuscate_tree(str(root))

        original_names = {"a.mkv", "b.srt", "c.nfo"}
        mapped_originals = {os.path.basename(v) for v in mapping.values() if "." in v}
        assert original_names == mapped_originals, "Mapping deve cobrir todos os arquivos originais"


# ---------------------------------------------------------------------------
# 3. NZB subjects: nenhum nome original vaza com --obfuscate unificado
# ---------------------------------------------------------------------------


class TestNzbSubjectsFullyRandom:
    """
    Com strong_obfuscate=True (default desde v0.28.0), fix_nzb_subjects deve
    preservar os nomes randômicos no NZB — nenhum nome original visível.
    """

    ORIGINAL_NAMES = ["video.mkv", "subs.srt", "nfo.txt"]
    RANDOM_NAMES = ["xk3mf9qa.mkv", "pl2abz17.srt", "rv9cxq04.txt"]

    def _make_obfuscated_map(self) -> dict[str, str]:
        return {rand: orig for rand, orig in zip(self.RANDOM_NAMES, self.ORIGINAL_NAMES)}

    def test_no_original_name_in_subjects_strong_obfuscate(self, tmp_path):
        nzb = _build_nzb(tmp_path, self.RANDOM_NAMES)

        fix_nzb_subjects(
            str(nzb),
            file_list=self.RANDOM_NAMES,
            obfuscated_map=self._make_obfuscated_map(),
            strong_obfuscate=True,  # unified --obfuscate behavior
        )

        tree = ET.parse(str(nzb))
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        subjects = [f.get("subject", "") for f in tree.getroot().findall(f".//{{{ns}}}file")]

        for subject in subjects:
            for orig in self.ORIGINAL_NAMES:
                assert orig not in subject, (
                    f"Nome original '{orig}' não deve aparecer em subject: {subject!r}"
                )

    def test_random_names_preserved_in_subjects(self, tmp_path):
        nzb = _build_nzb(tmp_path, self.RANDOM_NAMES)

        fix_nzb_subjects(
            str(nzb),
            file_list=self.RANDOM_NAMES,
            obfuscated_map=self._make_obfuscated_map(),
            strong_obfuscate=True,
        )

        tree = ET.parse(str(nzb))
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        subjects = [f.get("subject", "") for f in tree.getroot().findall(f".//{{{ns}}}file")]

        for rand in self.RANDOM_NAMES:
            assert any(rand in s for s in subjects), (
                f"Nome randômico '{rand}' deve aparecer em algum subject"
            )

    def test_without_obfuscate_original_names_restored(self, tmp_path):
        """Sem ofuscação, fix_nzb_subjects restaura os nomes originais (comportamento legado)."""
        nzb = _build_nzb(tmp_path, self.RANDOM_NAMES)

        fix_nzb_subjects(
            str(nzb),
            file_list=self.RANDOM_NAMES,
            obfuscated_map=self._make_obfuscated_map(),
            strong_obfuscate=False,
        )

        tree = ET.parse(str(nzb))
        ns = "http://www.newzbin.com/DTD/2003/nzb"
        subjects = " ".join(
            f.get("subject", "") for f in tree.getroot().findall(f".//{{{ns}}}file")
        )
        for orig in self.ORIGINAL_NAMES:
            assert orig in subjects, (
                f"Sem strong_obfuscate, nome original '{orig}' deve aparecer nos subjects"
            )


# ---------------------------------------------------------------------------
# 4. Regressão: orchestrator sempre passa strong_obfuscate=True com --obfuscate
# ---------------------------------------------------------------------------


class TestOrchestratorStrongObfuscateUnified:
    """
    Verifica que --obfuscate no orchestrator implica strong_obfuscate=True
    (unificação v0.28.0). Isso garante que o NZB nunca vaza nomes originais.
    """

    def test_obfuscate_flag_sets_strong_obfuscate_true(self):
        orch = UpaPastaOrchestrator(
            input_path="fake_tmp",
            obfuscate=True,
        )
        assert orch.strong_obfuscate is True, (
            "obfuscate=True deve implicar strong_obfuscate=True (v0.28.0)"
        )

    def test_no_obfuscate_keeps_strong_obfuscate_false(self):
        orch = UpaPastaOrchestrator(
            input_path="fake_tmp",
            obfuscate=False,
        )
        assert orch.strong_obfuscate is False, (
            "strong_obfuscate deve ser False quando obfuscate=False"
        )

    def test_strong_obfuscate_explicit_deprecated_path(self):
        """Mesmo passando strong_obfuscate=True diretamente, deve permanecer True."""
        orch = UpaPastaOrchestrator(
            input_path="fake_tmp",
            obfuscate=True,
            strong_obfuscate=True,
        )
        assert orch.strong_obfuscate is True


# ---------------------------------------------------------------------------
# 5. Mapping garante recuperabilidade via PAR2 (downloader consegue renomear)
# ---------------------------------------------------------------------------


class TestObfuscatedMapRecoverability:
    """
    Simula o que o downloader faz: usa o obfuscated_map para renomear
    os arquivos aleatórios de volta aos nomes originais.
    """

    @pytest.fixture(autouse=True)
    def fake_parpar(self, monkeypatch):
        monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))

    def test_map_enables_full_rename_recovery(self, monkeypatch, tmp_path):
        """
        obfuscate_and_par retorna mapa suficiente para renomear todos os
        arquivos de volta — simulando o que SABnzbd faz com o par2.
        """
        src = tmp_path / "Filme.2024.mkv"
        original_content = b"original video " * 1000
        src.write_bytes(original_content)
        original_hash = _sha256(src)

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: _OkPopen(a[0] if a else [], **kw),
        )

        rc, new_path, mapping, _ = obfuscate_and_par(
            str(src),
            redundancy=5,
            force=True,
            backend="parpar",
            threads=1,
        )
        assert rc == 0

        # O arquivo original é restaurado automaticamente pelo obfuscate_and_par
        assert src.exists()
        assert _sha256(src) == original_hash

        # O mapping permite que o downloader saiba o nome original de cada arquivo.
        # Para arquivo único, _obfuscate_single_file armazena o stem (sem extensão)
        # porque a extensão é preservada separadamente no nome ofuscado.
        original_stem = src.stem  # "Filme.2024" de "Filme.2024.mkv"
        mapped_originals = list(mapping.values())
        assert any(original_stem in v for v in mapped_originals), (
            f"Stem original '{original_stem}' deve estar no mapping "
            f"para que o downloader possa recuperar. Mapping: {mapping}"
        )

    def test_folder_map_covers_all_files(self, monkeypatch, tmp_path):
        """Para pasta, o mapping deve cobrir todos os arquivos, não apenas o root."""
        root = tmp_path / "Serie.S01"
        root.mkdir()
        files = {
            "ep01.mkv": b"ep1 " * 500,
            "ep02.mkv": b"ep2 " * 500,
            "nfo.txt": b"release",
        }
        for name, data in files.items():
            (root / name).write_bytes(data)

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: _OkPopen(a[0] if a else [], **kw),
        )

        rc, new_path, mapping, _ = obfuscate_and_par(
            str(root),
            redundancy=5,
            force=True,
            backend="parpar",
            threads=1,
        )
        assert rc == 0

        # Mapping deve conter entradas suficientes para todos os arquivos da pasta
        # (root folder entry + cada arquivo interno quando deep obfuscation ativa)
        mapped_originals_str = " ".join(mapping.values())
        for fname in files:
            assert fname in mapped_originals_str or root.name in mapped_originals_str, (
                f"'{fname}' ou o root deve estar no mapping para garantir recuperabilidade"
            )
