import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from upapasta.orchestrator import UpaPastaOrchestrator


class TestFolderObfuscation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_folder_obfuscation_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.sub_dir = self.test_dir / "sub"
        self.sub_dir.mkdir(exist_ok=True)
        self.test_file = self.sub_dir / "file.txt"
        with open(self.test_file, "w") as f:
            f.write("This is a test file inside a sub-folder.")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        # Remove pasta ofuscada (nome aleatório de 12 chars) que possa ter sobrado
        for item in Path(".").glob("*"):
            if item.is_dir() and len(item.name) == 12 and item.name.isalnum():
                shutil.rmtree(item, ignore_errors=True)
            # Remove par2 files gerados
            if item.is_file() and item.suffix == ".par2" and len(item.stem) >= 12:
                item.unlink(missing_ok=True)

    @patch('upapasta.orchestrator.check_or_prompt_credentials')
    @patch('upapasta.upfolder.find_nyuu', return_value='/usr/local/bin/nyuu')
    @patch('upapasta.upfolder.managed_popen')
    def test_folder_obfuscation_workflow(self, mock_managed_popen: MagicMock, mock_find_nyuu: MagicMock, mock_check_creds: MagicMock):
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_managed_popen.return_value.__enter__.return_value = mock_proc

        mock_check_creds.return_value = {
            "NNTP_HOST": "dummy", "NNTP_USER": "dummy", "NNTP_PASS": "dummy", "USENET_GROUP": "dummy"
        }

        orchestrator = UpaPastaOrchestrator(
            input_path=str(self.test_dir),
            dry_run=False,
            skip_upload=False,
            skip_rar=True,
            force=True,
            obfuscate=True,
            keep_files=True,
            env_file="/dev/null"
        )
        # Com o fix de hardlinks, a pasta original DEVE continuar existindo durante todo o processo
        # e os arquivos internos devem ter o mesmo inode (hardlink).
        self.assertTrue(self.test_dir.exists(), "A pasta original deve continuar existindo (hardlinks).")
        original_inode = self.test_file.stat().st_ino

        result = orchestrator.run()
        self.assertEqual(result, 0, f"O orquestrador deve retornar 0. rc={result}")

        # Após o workflow, a pasta original continua lá
        self.assertTrue(self.test_dir.exists(), "A pasta original deve permanecer após o upload.")
        self.assertEqual(self.test_file.stat().st_ino, original_inode, "O inode do arquivo original não deve mudar.")

        # O mapeamento deve ter a relação ofuscado → original
        self.assertTrue(orchestrator.obfuscated_map, "obfuscated_map deve ser preenchido.")
        # Com deep obfuscation, o map tem vários itens. O root é aquele cujo valor é o base original.
        original_base = self.test_dir.name
        obf_base = None
        for k, v in orchestrator.obfuscated_map.items():
            if v == original_base:
                obf_base = k
                break

        self.assertIsNotNone(obf_base, "Não foi possível encontrar o nome ofuscado da raiz no mapa.")

        # A "visão" ofuscada (links) deve ter sido mantida pelo cleanup (devido ao keep_files=True)
        obf_path = self.test_dir.parent / obf_base
        self.assertTrue(obf_path.exists(), f"Links de ofuscação '{obf_base}' devem ter sido mantidos (keep_files=True).")

        # O subject deve ser o nome ofuscado (não o original)
        self.assertEqual(orchestrator.subject, obf_base)

        # nyuu deve ter sido chamado
        self.assertTrue(mock_managed_popen.called, "nyuu deveria ter sido chamado.")

        # --obfuscate sem --password não gera senha (fluxo moderno 2026: ofuscação + PAR2, sem RAR)
        self.assertIsNone(orchestrator.rar_password, "--obfuscate sozinho não deve gerar senha.")

if __name__ == "__main__":
    unittest.main()
