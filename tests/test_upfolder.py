import io

from upapasta.upfolder import upload_to_usenet


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

    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    import upapasta.nfo as _nfo_mod
    monkeypatch.setattr(_nfo_mod, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    def mock_gen_nfo(src, dst):
        with open(dst, "w") as f:
            f.write("MediaInfo Test Content\nVideo: 1\nAudio: 2\n")
        return True

    monkeypatch.setattr(_nfo_mod, "generate_nfo_single_file", mock_gen_nfo)
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
    for i, line in enumerate(lines):
        if 'Comando nyuu (dry-run):' in line:
            if i + 1 < len(lines):
                cmd_line = lines[i + 1]
            break
    assert cmd_line is not None
    assert 'video.mkv' in cmd_line
    assert 'video.par2' in cmd_line
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

    class DummyCompletedProcess:
        def __init__(self, stdout: str = ""):
            self.stdout = stdout

    def fake_run(args, capture_output=False, text=False, check=False, cwd=None):
        return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\nAudio: 2\n")

    import upapasta.nfo as _nfo_mod
    monkeypatch.setattr(_nfo_mod, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    def mock_gen_nfo(src, dst):
        with open(dst, "w") as f:
            f.write("MediaInfo Test Content\nVideo: 1\nAudio: 2\n")
        return True

    monkeypatch.setattr(_nfo_mod, "generate_nfo_single_file", mock_gen_nfo)
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

    # Capture the args passed to nyuu (the non-mediainfo call)
    captured = {}

    class DummyCompletedProcess:
        def __init__(self, stdout: str = "", returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(args, **kwargs):
        # If calling mediainfo, return test stdout
        if args and (args[0].endswith('mediainfo') or args[0] == '/usr/bin/mediainfo'):
            return DummyCompletedProcess(stdout="MediaInfo Test Content\nVideo: 1\n")
        # nyuu call is no longer via subprocess.run, it uses managed_popen
        return DummyCompletedProcess(returncode=0)

    class MockProc:
        def __init__(self, args):
            self.args = args
        def wait(self):
            captured['args'] = self.args
            return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    import upapasta.nfo as _nfo_mod
    monkeypatch.setattr(_nfo_mod, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    def mock_gen_nfo(src, dst):
        with open(dst, "w") as f:
            f.write("MediaInfo Test Content\nVideo: 1\nAudio: 2\n")
        return True

    monkeypatch.setattr(_nfo_mod, "generate_nfo_single_file", mock_gen_nfo)
    monkeypatch.setattr(upfolder.subprocess, "run", fake_run)
    monkeypatch.setattr(upfolder, "managed_popen", lambda args, **kw: MockProc(args))


    rc = upload_to_usenet(str(input_file), env_vars=env_vars, dry_run=False)
    assert rc == 0
    # Ensure nfo file exists
    nfo_path = tmp_path / "video.nfo"
    assert nfo_path.exists()
    # Ensure nyuu args were captured and do not include video.nfo
    assert 'args' in captured
    assert not any('video.nfo' in str(a) for a in captured['args'])

def test_upload_to_usenet_basic(monkeypatch, tmp_path):
    rar_file = tmp_path / "test.rar"
    rar_file.write_text("rar content")
    par2_file = tmp_path / "test.par2"
    par2_file.write_text("par2 content")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test"
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    class C:
        returncode = 0
        def wait(self): return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder, "managed_popen", lambda *a, **k: C())

    rc = upload_to_usenet(str(rar_file), env_vars)
    assert rc == 0

def test_upload_to_usenet_missing_rar(tmp_path):
    env_vars = {"NNTP_HOST": "h", "NNTP_USER": "u", "NNTP_PASS": "p", "USENET_GROUP": "g"}
    rc = upload_to_usenet(str(tmp_path / "missing.rar"), env_vars)
    assert rc == 1

def test_upload_to_usenet_missing_par2(tmp_path):
    rar_file = tmp_path / "test.rar"
    rar_file.write_text("c")
    env_vars = {"NNTP_HOST": "h", "NNTP_USER": "u", "NNTP_PASS": "p", "USENET_GROUP": "g"}
    rc = upload_to_usenet(str(rar_file), env_vars)
    assert rc == 3

def test_upload_to_usenet_missing_creds(tmp_path):
    rar_file = tmp_path / "test.rar"
    rar_file.write_text("c")
    par2_file = tmp_path / "test.par2"
    par2_file.write_text("p")
    rc = upload_to_usenet(str(rar_file), {})
    assert rc == 2
