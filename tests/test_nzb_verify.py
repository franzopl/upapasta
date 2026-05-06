"""Testes para _verify_nzb e retry de upload."""
from upapasta.upfolder import _verify_nzb, upload_to_usenet

NZB_VALID = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
  <file poster="anon" date="0" subject="test">
    <groups><group>alt.binaries.test</group></groups>
    <segments><segment bytes="1" number="1">msgid@host</segment></segments>
  </file>
</nzb>
"""

NZB_NO_FILES = """\
<?xml version="1.0" encoding="UTF-8"?>
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
</nzb>
"""

NZB_MALFORMED = "this is not xml <<<"


def test_verify_nzb_valid(tmp_path):
    nzb = tmp_path / "test.nzb"
    nzb.write_text(NZB_VALID)
    assert _verify_nzb(str(nzb)) is True


def test_verify_nzb_no_files(tmp_path):
    nzb = tmp_path / "test.nzb"
    nzb.write_text(NZB_NO_FILES)
    assert _verify_nzb(str(nzb)) is False


def test_verify_nzb_malformed(tmp_path):
    nzb = tmp_path / "test.nzb"
    nzb.write_text(NZB_MALFORMED)
    assert _verify_nzb(str(nzb)) is False


def test_verify_nzb_empty(tmp_path):
    nzb = tmp_path / "test.nzb"
    nzb.write_bytes(b"")
    assert _verify_nzb(str(nzb)) is False


def test_verify_nzb_missing():
    assert _verify_nzb("/tmp/this_file_does_not_exist_upapasta.nzb") is False


def test_upload_retry_on_failure(tmp_path, monkeypatch):
    """upload_to_usenet deve tentar N+1 vezes antes de desistir."""
    import time
    monkeypatch.setattr(time, "sleep", lambda x: None)

    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy")
    par2 = tmp_path / "video.par2"
    par2.write_text("PAR2")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    call_count = {"n": 0}

    class MockProc:
        def wait(self):
            call_count["n"] += 1
            return 5
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder, "managed_popen", lambda *a, **kw: MockProc())

    rc = upload_to_usenet(str(input_file), env_vars=env_vars, upload_retries=2)

    assert rc == 5
    assert call_count["n"] == 3  # 1 original + 2 retries


def test_upload_retry_succeeds_on_second_try(tmp_path, monkeypatch):
    """upload_to_usenet deve ter sucesso na segunda tentativa."""
    import time
    monkeypatch.setattr(time, "sleep", lambda x: None)

    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy")
    par2 = tmp_path / "video.par2"
    par2.write_text("PAR2")

    env_vars = {
        "NNTP_HOST": "news.example.com",
        "NNTP_PORT": "563",
        "NNTP_USER": "user",
        "NNTP_PASS": "pass",
        "USENET_GROUP": "alt.binaries.test",
    }

    import upapasta.upfolder as upfolder
    monkeypatch.setattr(upfolder, "find_nyuu", lambda: "/bin/true")

    call_count = {"n": 0}

    class MockProc:
        def wait(self):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return 5
            return 0
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(upfolder, "managed_popen", lambda *a, **kw: MockProc())

    rc = upload_to_usenet(str(input_file), env_vars=env_vars, upload_retries=1)

    assert rc == 0
    assert call_count["n"] == 2
