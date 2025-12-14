import os
import tempfile
from pathlib import Path
import shutil
from upapasta.upfolder import upload_to_usenet
import io
import contextlib


def test_upload_to_usenet_dry_run_single_file(monkeypatch, tmp_path):
    # Create a dummy input file and a dummy par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")

    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Setup env_vars with credentials
    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
    }

    # Monkeypatch find_nyuu to avoid requiring nyuu on PATH
    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    # Now call upload_to_usenet with dry_run True
    import io
    import contextlib

    # Monkeypatch find_mediainfo and subprocess.run to return fake mediainfo output for capture
    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")
    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    stdout = out.getvalue()
    assert rc == 0
    # The .nfo should be generated locally but never uploaded to Usenet
    # Ensure .nfo is not present in the nyuu command line
    lines = stdout.splitlines()
    cmd_line = None
    for i, l in enumerate(lines):
        if 'Comando nyuu (dry-run):' in l:
            if i + 1 < len(lines):
                cmd_line = lines[i + 1]
            break
    assert cmd_line is not None
    assert 'video.nfo' not in cmd_line


def test_upload_single_file_generates_nfo(monkeypatch, tmp_path):
    # Create a dummy input file and a dummy par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")

    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Setup env_vars with credentials
    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
    }

    import upapasta.upfolder as upfolder
    # Monkeypatch find_nyuu to avoid requiring nyuu on PATH
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    # Monkeypatch find_mediainfo and subprocess.run to return fake mediainfo output
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    out = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    stdout = out.getvalue()
    assert rc == 0
    # Verify that .nfo file was created with expected content
    nfo_name = "video.nfo"
    nfo_path = tmp_path / nfo_name
    assert nfo_path.exists()
    content = nfo_path.read_text()
    assert "MediaInfo Test Content" in content
    # And ensure that it wasn't included in the nyuu command; it should not be uploaded
    lines = stdout.splitlines()
    cmd_line = None
    for i, l in enumerate(lines):
        if 'Comando nyuu (dry-run):' in l:
            if i + 1 < len(lines):
                cmd_line = lines[i + 1]
            break
    assert cmd_line is not None
    assert 'video.nfo' not in cmd_line


def test_upload_single_file_generates_nfo_in_nzb_out_dir(monkeypatch, tmp_path):
    # Create dummy input and par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")
    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Create a separate dir which will be the NZB_OUT destination
    nzb_dir = tmp_path / "nzb_dest"
    nzb_dir.mkdir()

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
        "NZB_OUT": str(nzb_dir / "{filename}.nzb"),
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    assert rc == 0

    # Ensure the nfo was created in the nzb_out directory and not in the input file dir
    nfo_path_in_nzb_dir = nzb_dir / "video.nfo"
    nfo_path_in_input_dir = tmp_path / "video.nfo"
    assert nfo_path_in_nzb_dir.exists()
    assert not nfo_path_in_input_dir.exists()


def test_upload_single_file_non_dry_run_does_not_upload_nfo(monkeypatch, tmp_path):
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")
    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    # Capture the args passed to nyuu (the non-mediainfo call)
    captured = {}

    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, **kwargs):
        # If calling mediainfo, return test stdout
        if args and (args[0].endswith('mediainfo') or args[0] == '/usr/bin/mediainfo'):
            return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\n")
        # Otherwise, it's the nyuu call; capture the args and return a dummy success
        captured['args'] = args
        class C:
            returncode = 0
        return C()

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=False)
    assert rc == 0
    # Ensure nfo file exists
    nfo_path = tmp_path / "video.nfo"
    assert nfo_path.exists()
    # Ensure nyuu args were captured and do not include video.nfo
    assert 'args' in captured
    assert not any('video.nfo' in str(a) for a in captured['args'])


def test_upload_nzb_conflict_rename(monkeypatch, tmp_path):
    # Create dummy input and par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")
    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Create a separate dir which will be the NZB_OUT destination and pre-create the NZB
    nzb_dir = tmp_path / "nzb_dest"
    nzb_dir.mkdir()
    existing_nzb = nzb_dir / "video.nzb"
    existing_nzb.write_text("old nzb content")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
        "NZB_OUT": str(nzb_dir / "{filename}.nzb"),
        # No NZB_CONFLICT -> default should be rename
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    out = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    stdout = out.getvalue()
    assert rc == 0
    # Ensure the -o option uses a new filename (not 'video.nzb') because rename is default
    assert "-o" in stdout
    # But there must be a different candidate used if the command shows a -o argument
    for line in stdout.splitlines():
        if 'Comando nyuu (dry-run):' in line:
            idx = stdout.splitlines().index(line)
            if idx + 1 < len(stdout.splitlines()):
                cmd_line = stdout.splitlines()[idx + 1]
                break
    # There should be "video-" suffix used in the output `-o` if rename took effect
    assert ('video-' in cmd_line) and ('video.nzb' not in cmd_line)


def test_upload_nzb_conflict_fail(monkeypatch, tmp_path):
    # Create dummy input and par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")
    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Create a separate dir which will be the NZB_OUT destination and pre-create the NZB
    nzb_dir = tmp_path / "nzb_dest"
    nzb_dir.mkdir()
    existing_nzb = nzb_dir / "video.nzb"
    existing_nzb.write_text("old nzb content")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
        "NZB_OUT": str(nzb_dir / "{filename}.nzb"),
        "NZB_CONFLICT": "fail",
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    # Expect a non-zero exit code for conflict (we use 6)
    assert rc == 6


def test_upload_nzb_conflict_overwrite(monkeypatch, tmp_path):
    # Create dummy input and par2
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")
    par2_file = tmp_path / "video.par2"
    par2_file.write_text("PAR2")

    # Create a separate dir which will be the NZB_OUT destination and pre-create the NZB
    nzb_dir = tmp_path / "nzb_dest"
    nzb_dir.mkdir()
    existing_nzb = nzb_dir / "video.nzb"
    existing_nzb.write_text("old nzb content")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
        "NZB_OUT": str(nzb_dir / "{filename}.nzb"),
        "NZB_CONFLICT": "overwrite",
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    out = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=True)
    stdout = out.getvalue()
    assert rc == 0
    # Overwrite (overwrite) should result in -O being included in nyuu command args
    for line in stdout.splitlines():
        if 'Comando nyuu (dry-run):' in line:
            idx = stdout.splitlines().index(line)
            if idx + 1 < len(stdout.splitlines()):
                cmd_line = stdout.splitlines()[idx + 1]
                break
    assert ' -O ' in cmd_line or cmd_line.endswith(' -O') or cmd_line.startswith('-O ')


def test_upload_folder_skip_rar_nzb_naming(monkeypatch, tmp_path):
    # Create a dummy folder with a file
    input_folder = tmp_path / "test_folder"
    input_folder.mkdir()
    test_file = input_folder / "file.txt"
    test_file.write_text("dummy content")

    # Create dummy par2 files
    par2_file = tmp_path / "test_folder.par2"
    par2_file.write_text("PAR2")

    # Setup env_vars with credentials
    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
    }

    # Monkeypatch find_nyuu to avoid requiring nyuu on PATH
    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    # Monkeypatch find_mediainfo and subprocess.run to return fake mediainfo output
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")
    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_folder), env_vars=env_vars, dry_run=True, skip_rar=True)
    stdout = out.getvalue()
    assert rc == 0

    # Check that NZB output path is "test_folder.nzb" (not "test_folder_content.nzb")
    # In dry-run mode, check the nyuu command contains -o test_folder.nzb
    assert " -o test_folder.nzb " in stdout


def test_upload_folder_skip_rar_nzb_naming(monkeypatch, tmp_path):
    # Create a dummy folder with a file
    input_folder = tmp_path / "test_folder"
    input_folder.mkdir()
    test_file = input_folder / "file.txt"
    test_file.write_text("dummy content")

    # Create dummy par2 files
    par2_file = tmp_path / "test_folder.par2"
    par2_file.write_text("PAR2")

    # Setup env_vars with credentials
    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
        "NNTP_SSL": "true",
    }

    # Monkeypatch find_nyuu to avoid requiring nyuu on PATH
    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    # Monkeypatch find_mediainfo and subprocess.run to return fake mediainfo output
    monkeypatch.setattr(upfolder, "find_mediainfo", lambda: "/usr/bin/mediainfo")
    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = upload_to_usenet(str(input_folder), env_vars=env_vars, dry_run=True, skip_rar=True)
    stdout = out.getvalue()
    assert rc == 0

    # Check that NZB output path is "test_folder.nzb" (not "test_folder_content.nzb")
    # In dry-run mode, check the nyuu command contains -o test_folder.nzb
    assert " -o test_folder.nzb " in stdout
