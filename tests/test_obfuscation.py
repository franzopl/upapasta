
import os
import shutil
import unittest
from pathlib import Path
from upapasta.orchestrator import UpaPastaOrchestrator

class TestObfuscation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_obfuscation_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.test_file = self.test_dir / "original_file.txt"
        with open(self.test_file, "w") as f:
            f.write("This is a test file.")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_obfuscation_workflow(self):
        """Arquivo único com --obfuscate: cria RAR com nome aleatório, original intacto."""
        orchestrator = UpaPastaOrchestrator(
            input_path=str(self.test_file),
            dry_run=False,
            skip_upload=True,
            force=True,
            obfuscate=True,
            keep_files=True,
        )

        result = orchestrator.run()
        self.assertEqual(result, 0, "O orquestrador deve retornar 0 em caso de sucesso.")

        # Arquivo original permanece intacto (está dentro do RAR)
        self.assertTrue(self.test_file.exists(), "O arquivo original deve continuar existindo.")

        # Deve existir um RAR com nome aleatório (diferente do original)
        rar_files = list(self.test_dir.glob("*.rar"))
        self.assertTrue(len(rar_files) > 0, "Deve haver um arquivo RAR ofuscado.")
        obfuscated_rar = rar_files[0]
        self.assertNotEqual(
            obfuscated_rar.stem, self.test_file.stem,
            "O nome do RAR ofuscado deve ser diferente do arquivo original."
        )

        # Arquivo de paridade criado para o RAR ofuscado
        par2_file = obfuscated_rar.with_suffix(".par2")
        self.assertTrue(par2_file.exists(), f"O arquivo de paridade {par2_file} deve existir.")

if __name__ == "__main__":
    unittest.main()
