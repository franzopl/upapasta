from upapasta.orchestrator import UpaPastaOrchestrator


def test_orchestrator_file_skip_rar_sets_input_target_and_skip_flag(tmp_path):
    """Sem --rar (skip_rar=True): arquivo único não deve criar RAR, input_target mantém caminho original."""
    temp_file = tmp_path / "video.mkv"
    temp_file.write_text("dummy content")

    orchestrator = UpaPastaOrchestrator(
        input_path=str(temp_file),
        dry_run=True,
        skip_rar=True,  # sem --rar: padrão correto
    )

    rc = orchestrator.run_makerar()
    assert rc is True
    assert orchestrator.skip_rar is True
    assert orchestrator.input_target == str(temp_file)


def test_orchestrator_file_with_rar_flag_creates_rar(tmp_path):
    """Com --rar (skip_rar=False): arquivo único deve criar RAR mesmo sem --obfuscate/--password."""
    temp_file = tmp_path / "video.mkv"
    temp_file.write_text("dummy content")

    orchestrator = UpaPastaOrchestrator(
        input_path=str(temp_file),
        dry_run=True,
        skip_rar=False,  # --rar explícito
    )

    rc = orchestrator.run_makerar()
    assert rc is True
    assert orchestrator.skip_rar is False  # não deve ser forçado para True
    expected_rar = str(temp_file.parent / "video.rar")
    assert orchestrator.input_target == expected_rar


def test_run_makerar_uses_generated_rar_path(tmp_path, monkeypatch):
    temp_dir = tmp_path / "Gravity.Falls.S02.720p.DSNP.WEB-DL.AAC2.0.H.264.DUAL-NeX"
    temp_dir.mkdir()

    def fake_make_rar(folder_path, force, threads=None, **kwargs):
        return 0, str(
            temp_dir / "Gravity.Falls.S02.720p.DSNP.WEB-DL.AAC2.0.H.264.DUAL-NeX.part001.rar"
        )

    monkeypatch.setattr("upapasta.orchestrator.make_rar", fake_make_rar)

    orchestrator = UpaPastaOrchestrator(
        input_path=str(temp_dir),
        dry_run=False,
        skip_rar=False,
    )

    rc = orchestrator.run_makerar()
    assert rc is True
    assert orchestrator.rar_file == str(
        temp_dir / "Gravity.Falls.S02.720p.DSNP.WEB-DL.AAC2.0.H.264.DUAL-NeX.part001.rar"
    )
    assert orchestrator.input_target == orchestrator.rar_file
