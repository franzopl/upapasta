from unittest.mock import patch

from upapasta.hooks import run_python_hooks


def test_run_python_hooks_loading(tmp_path, capsys):
    # Mock CONFIG_DIR to point to our tmp_path
    with patch("upapasta.hooks.CONFIG_DIR", str(tmp_path)):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        # Create a dummy hook
        hook_file = hooks_dir / "test_hook.py"
        hook_file.write_text("""
def on_upload_complete(metadata):
    print(f"HOOK_EXECUTED:{metadata['original_name']}")
""")

        metadata = {"original_name": "MyMovie.mkv"}
        run_python_hooks(metadata)

    captured = capsys.readouterr()
    assert "HOOK_EXECUTED:MyMovie.mkv" in captured.out


def test_run_python_hooks_resilience(tmp_path, capsys):
    # Test that a failing hook doesn't crash the program
    with patch("upapasta.hooks.CONFIG_DIR", str(tmp_path)):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        # Hook 1: Crashes
        hook1 = hooks_dir / "01_crash.py"
        hook1.write_text("def on_upload_complete(metadata): raise Exception('BOOM')")

        # Hook 2: Works
        hook2 = hooks_dir / "02_works.py"
        hook2.write_text("def on_upload_complete(metadata): print('HOOK_2_OK')")

        metadata = {"original_name": "test"}
        # Should not raise exception
        run_python_hooks(metadata)

    captured = capsys.readouterr()
    assert "Erro ao executar hook '01_crash.py'" in captured.out
    assert "HOOK_2_OK" in captured.out


def test_run_python_hooks_no_dir():
    # Should just return silently
    with patch("upapasta.hooks.CONFIG_DIR", "/non/existent/path"):
        run_python_hooks({})


def test_run_python_hooks_empty_dir(tmp_path):
    with patch("upapasta.hooks.CONFIG_DIR", str(tmp_path)):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        run_python_hooks({})
