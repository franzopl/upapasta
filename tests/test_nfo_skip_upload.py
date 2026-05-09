from upapasta.orchestrator import UpaPastaOrchestrator


def test_orchestrator_generates_nfo_even_with_skip_upload(tmp_path, monkeypatch):
    # Setup dummy input file
    input_file = tmp_path / "video.mkv"
    input_file.write_text("dummy video")

    # Mock NFO generation to avoid external dependencies (mediainfo)
    import upapasta.nfo as nfo_mod

    def mock_gen_nfo(src, dst, **kwargs):
        with open(dst, "w") as f:
            f.write("Fake NFO Content")
        return True

    monkeypatch.setattr(nfo_mod, "generate_nfo_single_file", mock_gen_nfo)
    monkeypatch.setattr(nfo_mod, "find_mediainfo", lambda: "/usr/bin/mediainfo")

    # Mock other steps to focus on NFO
    monkeypatch.setattr(UpaPastaOrchestrator, "run_makerar", lambda self, bar=None: True)
    monkeypatch.setattr(UpaPastaOrchestrator, "run_makepar", lambda self, bar=None: True)

    # Orchestrator with skip_upload=True
    orch = UpaPastaOrchestrator(
        input_path=str(input_file), skip_upload=True, dry_run=False, env_file=str(tmp_path / ".env")
    )

    # Create a fake .env
    with open(tmp_path / ".env", "w") as f:
        f.write("NZB_OUT_DIR=" + str(tmp_path) + "\n")
        f.write("USENET_GROUP=alt.binaries.test\n")

    rc = orch.run()
    assert rc == 0

    # Check if NFO was generated
    nfo_path = tmp_path / "video.nfo"
    assert nfo_path.exists(), "NFO file should be generated even with --skip-upload"
    assert nfo_path.read_text() == "Fake NFO Content"
    assert orch.nfo_file == str(nfo_path)
