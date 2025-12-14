
import os
import shutil
import unittest
from pathlib import Path
from upapasta.main import UpaPastaOrchestrator

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

        # Verificar se o arquivo original foi renomeado
        self.assertFalse(self.test_file.exists(), "O arquivo original não deve mais existir.")

        # Encontrar o arquivo ofuscado
        obfuscated_file = None
        for item in self.test_dir.iterdir():
            if item.is_file() and item.suffix == ".txt":
                obfuscated_file = item
                break
        
        self.assertIsNotNone(obfuscated_file, "Deve haver um arquivo ofuscado com a extensão .txt.")
        self.assertNotEqual(obfuscated_file.name, self.test_file.name, "O nome do arquivo ofuscado deve ser diferente do original.")

        # Verificar se os arquivos de paridade foram criados para o arquivo ofuscado
        par2_file = obfuscated_file.with_suffix(".par2")
        self.assertTrue(par2_file.exists(), f"O arquivo de paridade {par2_file} deve existir.")

if __name__ == "__main__":
    unittest.main()
