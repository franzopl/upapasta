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
        """Arquivo único com --obfuscate (sem --password): ofuscação + PAR2, sem RAR (fluxo moderno)."""
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

        # Arquivo original permanece intacto
        self.assertTrue(self.test_file.exists(), "O arquivo original deve continuar existindo.")

        # NÃO deve haver RAR (fluxo moderno: ofuscação + PAR2 direto)
        rar_files = list(self.test_dir.glob("*.rar"))
        self.assertEqual(len(rar_files), 0, "--obfuscate sem --password não deve criar RAR.")

        # Deve haver arquivo ofuscado (hardlink) com nome aleatório
        obfuscated_files = [f for f in self.test_dir.glob("*.txt") if f.name != self.test_file.name]
        self.assertTrue(len(obfuscated_files) > 0, "Deve haver um arquivo ofuscado (hardlink).")
        obfuscated_file = obfuscated_files[0]

        # Arquivo de paridade criado para o arquivo ofuscado
        par2_file = obfuscated_file.with_suffix(".par2")
        self.assertTrue(par2_file.exists(), f"O arquivo de paridade {par2_file} deve existir.")


if __name__ == "__main__":
    unittest.main()
