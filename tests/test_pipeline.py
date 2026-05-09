"""
Testes isolados para as classes e funções de _pipeline.py:
  - DependencyChecker
  - PathResolver
  - PipelineReporter
  - normalize_extensionless / revert_extensionless
  - do_cleanup_files
  - revert_obfuscation
  - recalculate_resources
"""

import os
from unittest.mock import MagicMock, patch

from upapasta._pipeline import (
    DependencyChecker,
    PathResolver,
    PipelineReporter,
    do_cleanup_files,
    normalize_extensionless,
    recalculate_resources,
    revert_extensionless,
    revert_obfuscation,
)

# ── DependencyChecker ─────────────────────────────────────────────────────────


class TestDependencyChecker:
    def test_missing_path_returns_false(self, tmp_path):
        assert DependencyChecker.validate(tmp_path / "nonexistent", dry_run=False) is False

    def test_existing_file_returns_true(self, tmp_path):
        f = tmp_path / "video.mkv"
        f.write_bytes(b"x" * 100)
        assert DependencyChecker.validate(f, dry_run=False) is True

    def test_existing_dir_returns_true(self, tmp_path):
        d = tmp_path / "folder"
        d.mkdir()
        (d / "file.txt").write_text("hi")
        assert DependencyChecker.validate(d, dry_run=False) is True

    def test_dry_run_skips_disk_check(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi")
        # In dry_run mode, disk usage is never checked, so even a mock of no free space is OK
        with patch("upapasta._pipeline.shutil.disk_usage") as mock_du:
            mock_du.return_value = MagicMock(free=0)
            # dry_run=True skips the disk check
            assert DependencyChecker.validate(f, dry_run=True) is True
            mock_du.assert_not_called()

    def test_insufficient_disk_returns_false(self, tmp_path):
        f = tmp_path / "bigfile.bin"
        f.write_bytes(b"x" * 1000)
        with patch("upapasta._pipeline.shutil.disk_usage") as mock_du:
            mock_du.return_value = MagicMock(free=0)
            assert DependencyChecker.validate(f, dry_run=False) is False


# ── PathResolver ──────────────────────────────────────────────────────────────


class TestPathResolver:
    def _make_resolver(self, tmp_path, skip_rar=True, subject="MyRelease"):
        return PathResolver(
            env_vars={},
            input_path=tmp_path / "input",
            skip_rar=skip_rar,
            nzb_conflict=None,
            subject=subject,
        )

    def test_par_file_path_single_rar(self):
        result = PathResolver.par_file_path("/some/dir/archive.rar")
        assert result == "/some/dir/archive.par2"

    def test_par_file_path_rar_volume(self):
        result = PathResolver.par_file_path("/some/dir/archive.part01.rar")
        assert result == "/some/dir/archive.par2"

    def test_par_file_path_plain_file(self):
        result = PathResolver.par_file_path("/some/dir/video.mkv")
        assert result == "/some/dir/video.par2"

    def test_check_nzb_conflict_skip_upload_returns_true(self, tmp_path):
        resolver = self._make_resolver(tmp_path)
        assert resolver.check_nzb_conflict(None, skip_upload=True, dry_run=False) is True

    def test_check_nzb_conflict_dry_run_returns_true(self, tmp_path):
        resolver = self._make_resolver(tmp_path)
        assert resolver.check_nzb_conflict(None, skip_upload=False, dry_run=True) is True

    def test_nfo_path_returns_string_pair(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NZB_OUT_DIR", str(tmp_path))
        resolver = PathResolver(
            env_vars={},
            input_path=tmp_path / "MyRelease",
            skip_rar=True,
            nzb_conflict=None,
            subject="MyRelease",
        )
        nfo_path, nzb_dir = resolver.nfo_path()
        assert nfo_path.endswith(".nfo")
        assert os.path.isabs(nfo_path)
        assert os.path.isabs(nzb_dir)


# ── PipelineReporter ──────────────────────────────────────────────────────────


class TestPipelineReporter:
    def test_collect_stats_missing_target(self):
        stats = PipelineReporter.collect_stats(None, None, None)
        assert stats["archive_size_mb"] == 0.0
        assert stats["par2_file_count"] == 0

    def test_collect_stats_nonexistent_target(self, tmp_path):
        stats = PipelineReporter.collect_stats(str(tmp_path / "missing.rar"), None, None)
        assert stats["archive_size_mb"] == 0.0

    def test_collect_stats_single_file(self, tmp_path):
        f = tmp_path / "archive.rar"
        f.write_bytes(b"x" * 1024 * 100)  # 100 KB
        stats = PipelineReporter.collect_stats(str(f), str(f), None)
        assert stats["archive_size_mb"] > 0

    def test_collect_stats_folder(self, tmp_path):
        d = tmp_path / "folder"
        d.mkdir()
        (d / "a.txt").write_bytes(b"x" * 512)
        (d / "b.txt").write_bytes(b"x" * 512)
        stats = PipelineReporter.collect_stats(str(d), None, None)
        assert stats["archive_size_mb"] > 0

    def test_collect_stats_par2_counted(self, tmp_path):
        f = tmp_path / "archive.rar"
        f.write_bytes(b"x" * 100)
        p1 = tmp_path / "archive.par2"
        p2 = tmp_path / "archive.vol0+1.par2"
        p1.write_bytes(b"x" * 50)
        p2.write_bytes(b"x" * 50)
        stats = PipelineReporter.collect_stats(str(f), str(f), str(p1))
        assert stats["par2_file_count"] == 2

    def test_print_header_runs(self, tmp_path, capsys):
        res = {
            "max_memory_mb": 1024,
            "total_gb": "1.0",
            "threads": 4,
            "par_threads": 4,
            "conservative_mode": False,
        }
        PipelineReporter.print_header(
            tmp_path,
            res,
            "MyRelease",
            "balanced",
            None,
            4,
            4,
            "auto",
            "auto",
            False,
            None,
            False,
            "N/A",
            10,
        )
        out = capsys.readouterr().out
        assert "UpaPasta" in out
        assert "MyRelease" in out

    def test_print_summary_runs(self, tmp_path, capsys):
        stats = {"archive_size_mb": 100.0, "par2_size_mb": 10.0, "par2_file_count": 2}
        PipelineReporter.print_summary(
            stats,
            tmp_path,
            "MyRelease",
            None,
            False,
            True,
            {},
            None,
            None,
            None,
            5.0,
        )
        out = capsys.readouterr().out
        assert "CONCLUÍDO" in out


# ── normalize_extensionless / revert_extensionless ────────────────────────────


class TestNormalizeExtensionless:
    def test_file_without_extension_renamed(self, tmp_path):
        f = tmp_path / "noext"
        f.write_text("data")
        mapping = normalize_extensionless(str(tmp_path))
        assert len(mapping) == 1
        new_path = list(mapping.keys())[0]
        assert new_path.endswith(".bin")
        assert os.path.exists(new_path)
        assert not os.path.exists(str(f))

    def test_file_with_extension_unchanged(self, tmp_path):
        f = tmp_path / "video.mkv"
        f.write_text("data")
        mapping = normalize_extensionless(str(tmp_path))
        assert len(mapping) == 0
        assert f.exists()

    def test_dotfile_unchanged(self, tmp_path):
        f = tmp_path / ".hidden"
        f.write_text("data")
        mapping = normalize_extensionless(str(tmp_path))
        assert len(mapping) == 0

    def test_revert_restores_names(self, tmp_path):
        f = tmp_path / "noext"
        f.write_text("data")
        mapping = normalize_extensionless(str(tmp_path))
        revert_extensionless(mapping)
        assert f.exists()
        assert not os.path.exists(str(tmp_path / "noext.bin"))

    def test_single_file_mode(self, tmp_path):
        f = tmp_path / "noext"
        f.write_text("data")
        mapping = normalize_extensionless(str(f))
        assert len(mapping) == 1


# ── do_cleanup_files ─────────────────────────────────────────────────────────


class TestDoCleanupFiles:
    def test_removes_par2_files(self, tmp_path, capsys):
        par = tmp_path / "archive.par2"
        par.write_bytes(b"x")
        do_cleanup_files(None, str(par), keep_files=False, on_error=False)
        assert not par.exists()

    def test_keep_files_skips_cleanup(self, tmp_path, capsys):
        par = tmp_path / "archive.par2"
        par.write_bytes(b"x")
        do_cleanup_files(None, str(par), keep_files=True, on_error=False)
        assert par.exists()

    def test_removes_rar_and_par2(self, tmp_path, capsys):
        rar = tmp_path / "archive.rar"
        par = tmp_path / "archive.par2"
        rar.write_bytes(b"x")
        par.write_bytes(b"x")
        do_cleanup_files(str(rar), str(par), keep_files=False, on_error=False)
        assert not rar.exists()
        assert not par.exists()

    def test_preserve_rar_flag(self, tmp_path, capsys):
        rar = tmp_path / "archive.rar"
        par = tmp_path / "archive.par2"
        rar.write_bytes(b"x")
        par.write_bytes(b"x")
        do_cleanup_files(str(rar), str(par), keep_files=False, on_error=True, preserve_rar=True)
        assert rar.exists()
        assert not par.exists()


# ── revert_obfuscation ────────────────────────────────────────────────────────


class TestRevertObfuscation:
    def test_no_obfuscate_returns_same_target(self, tmp_path):
        result = revert_obfuscation(
            obfuscate=False,
            input_target=str(tmp_path / "file.rar"),
            input_path=tmp_path / "file.rar",
            obfuscate_was_linked=False,
            obfuscated_map={},
            keep_files=False,
        )
        assert result == str(tmp_path / "file.rar")

    def test_linked_removes_obfuscated_file(self, tmp_path):
        original = tmp_path / "original.rar"
        obfuscated = tmp_path / "abcdef.rar"
        obfuscated.write_bytes(b"x")
        revert_obfuscation(
            obfuscate=True,
            input_target=str(obfuscated),
            input_path=original,
            obfuscate_was_linked=True,
            obfuscated_map={},
            keep_files=False,
        )
        assert not obfuscated.exists()

    def test_keep_files_skips_linked_removal(self, tmp_path):
        original = tmp_path / "original.rar"
        obfuscated = tmp_path / "abcdef.rar"
        obfuscated.write_bytes(b"x")
        revert_obfuscation(
            obfuscate=True,
            input_target=str(obfuscated),
            input_path=original,
            obfuscate_was_linked=True,
            obfuscated_map={},
            keep_files=True,
        )
        assert obfuscated.exists()

    def test_rename_restores_original_name(self, tmp_path):
        obfuscated = tmp_path / "xyz123.rar"
        obfuscated.write_bytes(b"x")
        original = tmp_path / "MyMovie.rar"
        revert_obfuscation(
            obfuscate=True,
            input_target=str(obfuscated),
            input_path=original,
            obfuscate_was_linked=False,
            obfuscated_map={},
            keep_files=False,
        )
        assert original.exists()
        assert not obfuscated.exists()


# ── recalculate_resources ─────────────────────────────────────────────────────


class TestRecalculateResources:
    def test_returns_dict_and_strings(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"x" * 1000)
        res, rar_src, par_src = recalculate_resources(f, None, None, None)
        assert isinstance(res, dict)
        assert "threads" in res
        assert "auto" in rar_src
        assert "auto" in par_src

    def test_manual_threads_labels(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"x" * 1000)
        _, rar_src, par_src = recalculate_resources(f, 4, 4, None)
        assert rar_src == "manual"
        assert par_src == "manual"
