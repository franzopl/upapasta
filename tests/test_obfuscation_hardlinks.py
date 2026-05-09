import io
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from upapasta.orchestrator import UpaPastaOrchestrator


class TestObfuscationHardlinks(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_hardlinks_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.test_file = self.test_dir / "video.mkv"
        with open(self.test_file, "w") as f:
            f.write("dummy video data")
        self.original_inode = self.test_file.stat().st_ino

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        # Cleanup any leftover obfuscated dirs
        for item in Path(".").glob("*"):
            if item.is_dir() and len(item.name) == 12 and item.name.isalnum():
                shutil.rmtree(item, ignore_errors=True)
            if item.is_file() and item.suffix == ".par2":
                item.unlink(missing_ok=True)

    @patch("upapasta.orchestrator.check_or_prompt_credentials")
    @patch("upapasta.upfolder.find_nyuu", return_value="/usr/local/bin/nyuu")
    @patch("upapasta.upfolder.managed_popen")
    def test_hardlink_preserves_original(
        self, mock_up_popen: MagicMock, mock_find_nyuu: MagicMock, mock_check_creds: MagicMock
    ):
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout = io.StringIO("")
        mock_up_popen.return_value.__enter__.return_value = mock_proc

        mock_check_creds.return_value = {
            "NNTP_HOST": "x",
            "NNTP_USER": "x",
            "NNTP_PASS": "x",
            "USENET_GROUP": "x",
        }

        orchestrator = UpaPastaOrchestrator(
            input_path=str(self.test_dir), skip_rar=True, obfuscate=True, env_file=os.devnull
        )

        result = orchestrator.run()
        self.assertEqual(result, 0)

        # Original must exist and have same inode
        self.assertTrue(self.test_file.exists())
        self.assertEqual(self.test_file.stat().st_ino, self.original_inode)

        # Obfuscated path should be gone
        obf_base = list(orchestrator.obfuscated_map.keys())[0]
        obf_path = self.test_dir.parent / obf_base
        self.assertFalse(obf_path.exists())

    @patch("upapasta.orchestrator.check_or_prompt_credentials")
    @patch("upapasta.makepar.managed_popen")
    @patch("os.link")
    def test_fallback_to_rename(
        self, mock_link: MagicMock, mock_par_popen: MagicMock, mock_creds: MagicMock
    ):
        # Simulate cross-device link failure
        mock_link.side_effect = OSError("Invalid cross-device link")

        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.side_effect = ["100%\n", ""]
        mock_par_popen.return_value.__enter__.return_value = mock_proc
        mock_creds.return_value = {
            "NNTP_HOST": "x",
            "NNTP_USER": "x",
            "NNTP_PASS": "x",
            "USENET_GROUP": "x",
        }

        orchestrator = UpaPastaOrchestrator(
            input_path=str(self.test_dir),
            skip_rar=True,
            skip_upload=True,  # focus on par phase
            obfuscate=True,
            env_file=os.devnull,
        )

        # We need to mock os.path.exists for the par2 file success check
        # Use a more careful mock to avoid recursion
        original_exists = os.path.exists

        def smart_exists(p):
            if str(p).endswith(".par2"):
                return True
            return original_exists(p)

        with patch("upapasta.orchestrator.os.path.exists", side_effect=smart_exists):
            result = orchestrator.run()

        self.assertEqual(result, 0)
        self.assertFalse(orchestrator.obfuscate_was_linked)

        # Original should be restored via rename back
        self.assertTrue(self.test_file.exists())


if __name__ == "__main__":
    unittest.main()
