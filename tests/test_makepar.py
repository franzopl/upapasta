import os
import tempfile
from pathlib import Path
import shutil
import io
import subprocess
from upapasta.makepar import make_parity


class DummyPopen:
    def __init__(self, args_passed=None, *args, **kwargs):
        # Simulate stdout iterator-like object
        self.stdout = io.StringIO("line1\nline2\n")
        self.args_passed = args_passed
    def wait(self):
        # Simulate the external tool creating the .par2 file referenced in the args
        try:
            # last argument(s) in args_passed are the input file(s); determine expected out_par2
            if self.args_passed:
                # Find '-o' parameter for parpar to locate output
                if '-o' in self.args_passed:
                    idx = self.args_passed.index('-o')
                    out_par2 = self.args_passed[idx + 1]
                    # create the par2 file to simulate tool output
                    open(out_par2, 'w').close()
        except Exception:
            pass
        return 0


def test_makepar_accepts_single_file_and_creates_par2(monkeypatch, tmp_path):
    # Create a dummy input file
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy content")

    # Monkeypatch find_parpar to return a fake executable
    import upapasta.makepar as makepar_module

    monkeypatch.setattr(makepar_module, "find_parpar", lambda: ("parpar", "/bin/true"))
    # Monkeypatch subprocess.Popen to our DummyPopen
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: DummyPopen(args[0] if args else None, **kwargs))

    out_par2 = tmp_path / "video.par2"

    rc = make_parity(str(input_file), redundancy=10, force=True, backend='parpar', threads=1, profile='balanced')
    assert rc == 0
    assert out_par2.exists()
