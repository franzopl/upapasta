"""Testes para _do_cleanup, cleanup e caminhos de erro críticos."""


from upapasta.orchestrator import UpaPastaOrchestrator


def _make_orchestrator(tmp_path, **kwargs):
    dummy = tmp_path / "input"
    dummy.mkdir()
    o = UpaPastaOrchestrator(input_path=str(dummy), dry_run=True, **kwargs)
    return o


# ---------------------------------------------------------------------------
# Cleanup remove RAR e PAR2 gerados
# ---------------------------------------------------------------------------

def test_cleanup_removes_rar_and_par2(tmp_path):
    rar = tmp_path / "show.rar"
    par = tmp_path / "show.par2"
    vol = tmp_path / "show.vol0+1.par2"
    rar.write_bytes(b"R")
    par.write_bytes(b"P")
    vol.write_bytes(b"V")

    o = _make_orchestrator(tmp_path)
    o.rar_file = str(rar)
    o.par_file = str(par)

    o.cleanup()

    assert not rar.exists()
    assert not par.exists()
    assert not vol.exists()


def test_cleanup_removes_multivolume_rar(tmp_path):
    for i in range(1, 4):
        (tmp_path / f"show.part{i:02d}.rar").write_bytes(b"R")
    par = tmp_path / "show.par2"
    par.write_bytes(b"P")

    o = _make_orchestrator(tmp_path)
    o.rar_file = str(tmp_path / "show.part01.rar")
    o.par_file = str(par)

    o.cleanup()

    remaining = list(tmp_path.glob("*.rar"))
    assert remaining == [], f"RAR volumes not removed: {remaining}"
    assert not par.exists()


def test_cleanup_keep_files_skips_deletion(tmp_path):
    rar = tmp_path / "show.rar"
    par = tmp_path / "show.par2"
    rar.write_bytes(b"R")
    par.write_bytes(b"P")

    o = _make_orchestrator(tmp_path, keep_files=True)
    o.rar_file = str(rar)
    o.par_file = str(par)

    o.cleanup()

    assert rar.exists()
    assert par.exists()


def test_cleanup_on_error_ignores_keep_files(tmp_path):
    rar = tmp_path / "show.rar"
    par = tmp_path / "show.par2"
    rar.write_bytes(b"R")
    par.write_bytes(b"P")

    o = _make_orchestrator(tmp_path, keep_files=True)
    o.rar_file = str(rar)
    o.par_file = str(par)

    o._cleanup_on_error()

    assert not rar.exists()
    assert not par.exists()


def test_cleanup_nonexistent_files_does_not_raise(tmp_path):
    o = _make_orchestrator(tmp_path)
    o.rar_file = str(tmp_path / "ghost.rar")
    o.par_file = str(tmp_path / "ghost.par2")
    o.cleanup()  # deve passar sem exceção


# ---------------------------------------------------------------------------
# run_makerar — caminho de erro
# ---------------------------------------------------------------------------

def test_run_makerar_rar_failure_returns_false(tmp_path, monkeypatch):
    folder = tmp_path / "MyShow"
    folder.mkdir()

    def fake_make_rar(path, force, threads=None, **kwargs):
        return 5, None  # código de erro

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)

    o = UpaPastaOrchestrator(input_path=str(folder), dry_run=False, skip_rar=False)
    result = o.run_makerar()
    assert result is False


def test_run_makerar_file_not_found_returns_false(tmp_path, monkeypatch):
    folder = tmp_path / "MyShow"
    folder.mkdir()

    def fake_make_rar(path, force, threads=None, **kwargs):
        raise FileNotFoundError("rar not found")

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)

    o = UpaPastaOrchestrator(input_path=str(folder), dry_run=False, skip_rar=False)
    result = o.run_makerar()
    assert result is False


# ---------------------------------------------------------------------------
# run_makepar — caminho de erro
# ---------------------------------------------------------------------------

def test_run_makepar_failure_returns_false(tmp_path, monkeypatch):
    target = tmp_path / "show.rar"
    target.write_bytes(b"R")

    def fake_make_parity(*args, **kwargs):
        return 5  # erro

    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)
    monkeypatch.setattr("upapasta.makepar.make_parity", fake_make_parity)

    o = UpaPastaOrchestrator(input_path=str(tmp_path), dry_run=False)
    o.input_target = str(target)
    result = o.run_makepar()
    assert result is False


def test_run_makepar_missing_binary_returns_false(tmp_path, monkeypatch):
    target = tmp_path / "show.rar"
    target.write_bytes(b"R")

    def fake_make_parity(*args, **kwargs):
        raise FileNotFoundError("parpar not found")

    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)

    o = UpaPastaOrchestrator(input_path=str(tmp_path), dry_run=False)
    o.input_target = str(target)
    result = o.run_makepar()
    assert result is False


# ---------------------------------------------------------------------------
# par_slice_size é passado ao make_parity
# ---------------------------------------------------------------------------

def test_par_slice_size_propagated(tmp_path, monkeypatch):
    target = tmp_path / "show.rar"
    target.write_bytes(b"R")
    par = tmp_path / "show.par2"
    par.write_bytes(b"P")

    captured = {}

    def fake_make_parity(*args, **kwargs):
        captured["slice_size"] = kwargs.get("slice_size")
        return 0

    monkeypatch.setattr("upapasta.orchestrator.make_parity", fake_make_parity)

    o = UpaPastaOrchestrator(input_path=str(tmp_path), dry_run=False, par_slice_size="2M")
    o.input_target = str(target)
    o.run_makepar()

    assert captured.get("slice_size") == "2M"
