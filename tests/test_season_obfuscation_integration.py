import os
import shutil
import secrets
import pytest

pytestmark = pytest.mark.skip(reason="testes de integração --season ainda não necessários")
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock
from contextlib import contextmanager

from upapasta.orchestrator import UpaPastaOrchestrator, UpaPastaSession
from upapasta.nzb import merge_nzbs, fix_season_nzb_subjects


@pytest.fixture
def mock_binaries(monkeypatch, tmp_path):
    # make_rar: não deve ser chamado em --skip-rar, mas mock por segurança
    def fake_make_rar(folder_path, force, threads=None, password=None):
        rar_path = Path(folder_path).with_suffix(".rar")
        rar_path.write_text("fake rar")
        return 0, str(rar_path)

    # obfuscate_and_par: cria pasta/arquivo ofuscado e par2 falsos
    def fake_obfuscate_and_par(input_path, **kwargs):
        input_p = Path(input_path)
        parent = input_p.parent
        obf_name = secrets.token_hex(6)

        if input_p.is_file():
            ext = input_p.suffix
            obf_path = parent / (obf_name + ext)
            shutil.copy2(str(input_p), str(obf_path))
            obf_map = {obf_name: input_p.stem}
            (parent / (obf_name + ".par2")).write_text("fake par2")
            (parent / (obf_name + ".vol0+1.par2")).write_text("fake par2 vol")
            return 0, str(obf_path), obf_map, False
        else:
            obf_path = parent / obf_name
            shutil.copytree(str(input_p), str(obf_path))
            obf_map = {obf_name: input_p.name}
            (parent / (obf_name + ".par2")).write_text("fake par2")
            (parent / (obf_name + ".vol0+1.par2")).write_text("fake par2 vol")
            return 0, str(obf_path), obf_map, False

    # make_parity: fallback para casos sem obfuscação
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
        return {"threads": 2, "par_threads": 2, "max_memory_mb": 512,
                "conservative_mode": False, "total_gb": 0.0}

    monkeypatch.setattr("upapasta.orchestrator.calculate_optimal_resources", fake_resources)

    @contextmanager
    def fake_managed_popen(cmd, **kwargs):
        # Extrai -o <nzb_path> do comando nyuu
        nzb_path = None
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                nzb_path = cmd[i + 1]
                break

        if nzb_path:
            # Detecta os arquivos passados ao nyuu (após as flags)
            files_to_post = []
            i = 0
            while i < len(cmd):
                arg = cmd[i]
                # Pula flags com valor
                if arg.startswith("-") and i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
                    i += 2
                    continue
                if not arg.startswith("-") and i > 0:
                    files_to_post.append(arg)
                i += 1

            ns = "http://www.newzbin.com/DTD/2003/nzb"
            root = ET.Element(f"{{{ns}}}nzb")
            for f in files_to_post:
                sub = os.path.basename(f) if os.path.isabs(f) else f
                file_elem = ET.SubElement(root, f"{{{ns}}}file")
                file_elem.set("subject", f'"{sub}" yEnc (1/1)')
                segs = ET.SubElement(file_elem, f"{{{ns}}}segments")
                seg = ET.SubElement(segs, f"{{{ns}}}segment")
                seg.set("number", "1")
                seg.text = "abc@def"

            ET.register_namespace("", ns)
            os.makedirs(os.path.dirname(os.path.abspath(nzb_path)), exist_ok=True)
            ET.ElementTree(root).write(nzb_path, encoding="UTF-8", xml_declaration=True)

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        yield mock_proc

    monkeypatch.setattr("upapasta._process.managed_popen", fake_managed_popen)
    monkeypatch.setattr("upapasta.upfolder.managed_popen", fake_managed_popen)
    monkeypatch.setattr("upapasta.nfo.generate_nfo_single_file", lambda *a, **k: True)
    monkeypatch.setattr("upapasta.nfo.generate_nfo_folder", lambda *a, **k: True)


@pytest.fixture
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


def test_season_obfuscation_integration(tmp_path, mock_binaries, dummy_env):
    """Verifica que o NZB consolidado da temporada tem subjects com prefixo ep_name/."""
    season_dir = tmp_path / "Season01"
    season_dir.mkdir()

    # Episódio 01: arquivo único
    ep01 = season_dir / "Episode01.mkv"
    ep01.write_text("ep01 content")

    # Episódio 02: pasta com arquivo
    ep02_dir = season_dir / "Episode02"
    ep02_dir.mkdir()
    (ep02_dir / "Video.mkv").write_text("ep02 content")

    items = sorted(f for f in season_dir.iterdir() if not f.name.startswith("."))
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
            assert o.generated_nzb is not None
            nzb_episode_data.append((o.generated_nzb, item.name))

    # Mescla NZBs
    nzb_dir = tmp_path / "nzbs"
    season_nzb_path = nzb_dir / "Season01.nzb"
    nzb_paths = [p for p, _ in nzb_episode_data]
    assert merge_nzbs(nzb_paths, str(season_nzb_path)) is True

    # Aplica correção de subjects (igual ao main.py)
    fix_season_nzb_subjects(str(season_nzb_path), nzb_episode_data)

    assert season_nzb_path.exists()

    ns = {"nzb": "http://www.newzbin.com/DTD/2003/nzb"}
    root = ET.parse(season_nzb_path).getroot()
    subjects = [f.get("subject", "") for f in root.findall("nzb:file", ns)]

    print("\nSubjects no NZB da temporada:")
    for s in subjects:
        print(f"  {s}")

    # Episódio 01 (arquivo único): subject deve conter o nome original
    assert any("Episode01.mkv" in s for s in subjects), \
        f"Episode01.mkv não encontrado nos subjects: {subjects}"

    # Episódio 02 (pasta): subject deve conter prefixo Episode02/
    assert any("Episode02/Video.mkv" in s for s in subjects), \
        f"Episode02/Video.mkv não encontrado nos subjects: {subjects}"
