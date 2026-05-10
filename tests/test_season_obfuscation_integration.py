from __future__ import annotations

import io
import os
import secrets
import shutil
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from upapasta.nzb import collect_season_nzbs, fix_season_nzb_subjects, merge_nzbs
from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession

NS = "http://www.newzbin.com/DTD/2003/nzb"


def _make_nzb(path: Path, subjects: list[str]) -> None:
    """Cria NZB mínimo válido com os subjects fornecidos."""
    ET.register_namespace("", NS)
    root = ET.Element(f"{{{NS}}}nzb")
    for subj in subjects:
        fe = ET.SubElement(root, f"{{{NS}}}file")
        fe.set("subject", subj)
        segs = ET.SubElement(fe, f"{{{NS}}}segments")
        seg = ET.SubElement(segs, f"{{{NS}}}segment")
        seg.set("number", "1")
        seg.text = "abc@def"
    ET.ElementTree(root).write(str(path), encoding="UTF-8", xml_declaration=True)


# ── Testes unitários de merge e fix_season ────────────────────────────────────


def test_season_mixed_file_and_folder_episodes(tmp_path):
    """Episódios-arquivo não recebem prefixo duplicado; episódios-pasta recebem prefixo."""
    # Simula o fluxo exato do main.py para uma temporada mista:
    #   Episode01.mkv  → arquivo único, subject já correto após fix_nzb_subjects
    #   Episode02/     → pasta, precisa de prefixo no season NZB
    ep01_nzb = tmp_path / "Episode01.nzb"
    ep02_nzb = tmp_path / "Episode02.nzb"
    season_nzb = tmp_path / "Season01.nzb"

    _make_nzb(ep01_nzb, ['"Episode01.mkv" yEnc (1/1)'])
    _make_nzb(ep02_nzb, ['"Episode02/Video.mkv" yEnc (1/1)', '"Episode02/Subs.srt" yEnc (1/1)'])

    all_nzbs = [str(ep01_nzb), str(ep02_nzb)]
    # Apenas episódios-pasta passam para fix_season_nzb_subjects
    folder_eps = [(str(ep02_nzb), "Episode02")]

    assert merge_nzbs(all_nzbs, str(season_nzb)) is True
    fix_season_nzb_subjects(str(season_nzb), folder_eps)

    ns = {"nzb": NS}
    root = ET.parse(season_nzb).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]

    # Arquivo único: subject inalterado, sem prefixo duplo
    assert any(s == '"Episode01.mkv" yEnc (1/1)' for s in subjects), subjects
    assert not any("Episode01.mkv/Episode01.mkv" in s for s in subjects), subjects
    # Pasta: subject com prefixo correto
    assert any("Episode02/Video.mkv" in s for s in subjects), subjects
    assert any("Episode02/Subs.srt" in s for s in subjects), subjects


def test_season_obfuscated_subjects_not_prefixed(tmp_path):
    """Com --obfuscate, fix_season_nzb_subjects NÃO é chamado: subjects permanecem ofuscados."""
    ep_nzb = tmp_path / "S01E01.nzb"
    season_nzb = tmp_path / "Season01.nzb"

    # Simula subjects gerados com strong_obfuscate=True (nomes hexadecimais)
    _make_nzb(ep_nzb, ['"a1b2c3d4.mkv" yEnc (1/1)', '"a1b2c3d4.par2" yEnc (1/1)'])
    merge_nzbs([str(ep_nzb)], str(season_nzb))

    # fix_season_nzb_subjects NÃO é chamado (args.obfuscate=True no main.py)
    # Verifica que subjects permanecem ofuscados sem prefixo de ep_name
    ns = {"nzb": NS}
    root = ET.parse(season_nzb).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]
    assert any('"a1b2c3d4.mkv"' in s for s in subjects), subjects
    assert not any("S01E01" in s for s in subjects), f"ep_name vazou: {subjects}"


def test_merge_nzbs_combines_files(tmp_path):
    a = tmp_path / "a.nzb"
    b = tmp_path / "b.nzb"
    out = tmp_path / "season.nzb"
    _make_nzb(a, ['"S01E01.mkv" yEnc (1/1)'])
    _make_nzb(b, ['"S01E02/Video.mkv" yEnc (1/1)'])

    assert merge_nzbs([str(a), str(b)], str(out)) is True
    ns = {"nzb": NS}
    root = ET.parse(out).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]
    assert len(subjects) == 2
    assert any("S01E01.mkv" in s for s in subjects)
    assert any("S01E02/Video.mkv" in s for s in subjects)


def test_fix_season_nzb_subjects_applies_prefix(tmp_path):
    """Subjects sem prefixo recebem o prefixo do episódio correto."""
    ep01_nzb = tmp_path / "ep01.nzb"
    ep02_nzb = tmp_path / "ep02.nzb"
    season_nzb = tmp_path / "season.nzb"

    _make_nzb(ep01_nzb, ['"S01E01.mkv" yEnc (1/1)'])
    _make_nzb(ep02_nzb, ['"Video.mkv" yEnc (1/1)', '"Subs.srt" yEnc (1/1)'])

    merge_nzbs([str(ep01_nzb), str(ep02_nzb)], str(season_nzb))

    episode_data = [(str(ep01_nzb), "S01E01"), (str(ep02_nzb), "S01E02")]
    fix_season_nzb_subjects(str(season_nzb), episode_data)

    ns = {"nzb": NS}
    root = ET.parse(season_nzb).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]

    assert any("S01E01/S01E01.mkv" in s for s in subjects), subjects
    assert any("S01E02/Video.mkv" in s for s in subjects), subjects
    assert any("S01E02/Subs.srt" in s for s in subjects), subjects


def test_fix_season_nzb_subjects_strips_existing_prefix(tmp_path):
    """Prefixo errado existente no subject é substituído pelo correto."""
    ep_nzb = tmp_path / "ep.nzb"
    season_nzb = tmp_path / "season.nzb"
    # Subject já tem prefixo obfuscado (ex: saído de fix_nzb_subjects)
    _make_nzb(ep_nzb, ['"old_prefix/Video.mkv" yEnc (1/1)'])
    merge_nzbs([str(ep_nzb)], str(season_nzb))

    fix_season_nzb_subjects(str(season_nzb), [(str(ep_nzb), "S01E01")])

    ns = {"nzb": NS}
    root = ET.parse(season_nzb).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]
    assert any("S01E01/Video.mkv" in s for s in subjects), subjects
    assert not any("old_prefix" in s for s in subjects), subjects


def test_collect_season_nzbs_fallback(tmp_path):
    """Fallback glob encontra NZBs pelo padrão de temporada."""
    (tmp_path / "ShowName.S01E01.nzb").write_text("<nzb/>")
    (tmp_path / "ShowName.S01E02.nzb").write_text("<nzb/>")
    # NZB da temporada — deve ser excluído
    (tmp_path / "ShowName.S01.nzb").write_text("<nzb/>")
    # Outro NZB sem S01 — deve ser excluído
    (tmp_path / "Outro.S02E01.nzb").write_text("<nzb/>")

    result = collect_season_nzbs(str(tmp_path), "ShowName.S01")
    stems = [Path(p).stem for p, _ in result]
    assert "ShowName.S01E01" in stems
    assert "ShowName.S01E02" in stems
    assert "ShowName.S01" not in stems
    assert "Outro.S02E01" not in stems


# ── Fixture de integração ─────────────────────────────────────────────────────


@pytest.fixture()
def mock_binaries(monkeypatch, tmp_path):
    def fake_make_rar(folder_path, force, threads=None, password=None):
        rar_path = Path(folder_path).with_suffix(".rar")
        rar_path.write_text("fake rar")
        return 0, str(rar_path)

    def fake_obfuscate_and_par(input_path, **kwargs):
        input_p = Path(input_path)
        parent = input_p.parent
        obf_name = secrets.token_hex(6)

        if input_p.is_file():
            ext = input_p.suffix
            obf_path = parent / (obf_name + ext)
            shutil.copy2(str(input_p), str(obf_path))
            obf_map = {obf_name: input_p.stem}
        else:
            obf_path = parent / obf_name
            shutil.copytree(str(input_p), str(obf_path))
            obf_map = {obf_name: input_p.name}

        (parent / (obf_name + ".par2")).write_text("fake par2")
        (parent / (obf_name + ".vol0+1.par2")).write_text("fake par2 vol")
        return 0, str(obf_path), obf_map, False

    def fake_make_parity(input_path, **kwargs):
        input_p = Path(input_path)
        par2 = input_p.parent / (input_p.stem + ".par2")
        par2.write_text("fake par2")
        (par2.with_suffix(".vol0+1.par2")).write_text("fake par2 vol")
        return 0

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)
    monkeypatch.setattr("upapasta.orchestrator.obfuscate_and_par", fake_obfuscate_and_par)
    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)
    monkeypatch.setattr("upapasta.upfolder.find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr("upapasta.upfolder.os.path.exists", lambda x: True)

    def fake_resources(*a, **k):
        return {
            "threads": 2,
            "par_threads": 2,
            "max_memory_mb": 512,
            "conservative_mode": False,
            "total_gb": 0.0,
        }

    monkeypatch.setattr(
        "upapasta.orchestrator.recalculate_resources",
        lambda *a, **k: (fake_resources(), "test", "test"),
    )

    @contextmanager
    def fake_managed_popen(cmd, cwd=None, **kwargs):
        nzb_path: str | None = None
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                nzb_path = cmd[i + 1]
                break

        if nzb_path:
            # Coleta arquivos passados ao final do comando (after all flags)
            files_to_post: list[str] = []
            i = 0
            while i < len(cmd):
                arg = cmd[i]
                if arg.startswith("-") and i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
                    i += 2
                    continue
                if not arg.startswith("-") and i > 0:
                    files_to_post.append(arg)
                i += 1

            root = ET.Element(f"{{{NS}}}nzb")
            for f in files_to_post:
                sub = os.path.basename(f) if os.path.isabs(f) else f
                fe = ET.SubElement(root, f"{{{NS}}}file")
                fe.set("subject", f'"{sub}" yEnc (1/1)')
                segs = ET.SubElement(fe, f"{{{NS}}}segments")
                seg = ET.SubElement(segs, f"{{{NS}}}segment")
                seg.set("number", "1")
                seg.text = "abc@def"

            ET.register_namespace("", NS)
            os.makedirs(os.path.dirname(os.path.abspath(nzb_path)), exist_ok=True)
            ET.ElementTree(root).write(nzb_path, encoding="UTF-8", xml_declaration=True)

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        # stdout precisa suportar .read() (usado por _read_output em _progress.py)
        mock_proc.stdout = io.BytesIO(b"")
        yield mock_proc

    monkeypatch.setattr("upapasta._process.managed_popen", fake_managed_popen)
    monkeypatch.setattr("upapasta.upfolder.managed_popen", fake_managed_popen)
    monkeypatch.setattr("upapasta.nfo.generate_nfo_single_file", lambda *a, **k: True)
    monkeypatch.setattr("upapasta.nfo.generate_nfo_folder", lambda *a, **k: True)


@pytest.fixture()
def dummy_env(tmp_path):
    nzb_dir = tmp_path / "nzbs"
    nzb_dir.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NNTP_HOST=localhost\n"
        "NNTP_PORT=119\n"
        "NNTP_USER=user\n"
        "NNTP_PASS=pass\n"
        "USENET_GROUP=alt.binaries.test\n"
        f"NZB_OUT_DIR={nzb_dir}\n"
    )
    return env_file


# ── Teste de integração ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_season_obfuscation_integration(tmp_path, mock_binaries, dummy_env):
    """NZB consolidado da temporada tem subjects com prefixo correto após obfuscação."""
    season_dir = tmp_path / "Season01"
    season_dir.mkdir()

    ep01 = season_dir / "Episode01.mkv"
    ep01.write_text("ep01 content")

    ep02_dir = season_dir / "Episode02"
    ep02_dir.mkdir()
    (ep02_dir / "Video.mkv").write_text("ep02 content")

    items = sorted(season_dir.iterdir())
    assert len(items) == 2

    nzb_episode_data: list[tuple[str, str]] = []

    for item in items:
        orch = UpaPastaOrchestrator(
            input_path=str(item),
            obfuscate=True,
            skip_rar=True,
            env_file=str(dummy_env),
            keep_files=True,
        )
        if item.is_dir():
            orch.nzb_subject_prefix = item.name

        with UpaPastaSession(orch) as o:
            rc = o.run()
            assert rc == 0, f"Episódio {item.name} falhou com rc={rc}"
            assert o.generated_nzb is not None, f"generated_nzb não foi populado para {item.name}"
            nzb_episode_data.append((o.generated_nzb, item.name))

    assert len(nzb_episode_data) == 2

    nzb_dir = tmp_path / "nzbs"
    season_nzb_path = nzb_dir / "Season01.nzb"
    nzb_paths = [p for p, _ in nzb_episode_data]
    assert merge_nzbs(nzb_paths, str(season_nzb_path)) is True

    fix_season_nzb_subjects(str(season_nzb_path), nzb_episode_data)

    assert season_nzb_path.exists()

    ns = {"nzb": NS}
    root = ET.parse(season_nzb_path).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]

    print("\nSubjects no NZB da temporada:")
    for s in subjects:
        print(f"  {s}")

    # Episódio arquivo único: subject contém o nome original
    assert any("Episode01.mkv" in s for s in subjects), f"Episode01.mkv não encontrado: {subjects}"
    # Episódio pasta: subject com prefixo Episode02/
    assert any("Episode02/Video.mkv" in s for s in subjects), (
        f"Episode02/Video.mkv não encontrado: {subjects}"
    )
