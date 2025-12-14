import os
import tempfile
from upapasta.main import UpaPastaOrchestrator


def test_orchestrator_file_skip_rar_sets_input_target_and_skip_flag(tmp_path):
    # Create a temp file to act as input
    temp_file = tmp_path / "video.mkv"
    temp_file.write_text("dummy content")

    orchestrator = UpaPastaOrchestrator(
        input_path=str(temp_file),
        dry_run=True,
        skip_rar=False,  # user did not explicitly set skip-rar
    )

    # Run the makerar step which should detect single-file and set skip_rar
    rc = orchestrator.run_makerar()
    assert rc is True
    assert orchestrator.skip_rar is True
    assert orchestrator.input_target == str(temp_file)
