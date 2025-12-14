import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from upapasta.main import UpaPastaOrchestrator

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
        
        # Cleanup obfuscated folders that might be left over
        for item in Path(".").glob("*"):
            if item.is_dir() and len(item.name) == 12: # Heuristic for random name
                shutil.rmtree(item, ignore_errors=True)


    @patch('upapasta.main.check_or_prompt_credentials')
    @patch('upapasta.upfolder.subprocess.run')
    def test_folder_obfuscation_workflow(self, mock_subprocess_run: MagicMock, mock_check_creds: MagicMock):
        # Mock para evitar a execução real do nyuu
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        # Mock credenciais
        mock_check_creds.return_value = {
            "NNTP_HOST": "dummy", "NNTP_USER": "dummy", "NNTP_PASS": "dummy", "USENET_GROUP": "dummy"
        }

        orchestrator = UpaPastaOrchestrator(
            input_path=str(self.test_dir),
            dry_run=False,
            skip_upload=False, # We need to run the upload part to check the command
            skip_rar=True, # Skip RAR to deal with the folder directly
            force=True,
            obfuscate=True,
            keep_files=True,
            # Mock env vars to prevent credential prompts
            env_file="/dev/null" 
        )
        
        result = orchestrator.run()
        self.assertEqual(result, 0, f"O orquestrador deve retornar 0. Log: {result}")

        # Verificar se a pasta original ainda existe
        self.assertTrue(self.test_dir.exists(), "A pasta original deve permanecer após a ofuscação.")

        # Verificar se o nyuu foi chamado
        self.assertTrue(mock_subprocess_run.called, "subprocess.run com o comando nyuu deveria ter sido chamado.")
        
        # Extrair o comando que foi passado para o subprocess
        call_args = mock_subprocess_run.call_args
        nyuu_command = call_args[0][0]

        # O nome da pasta ofuscada é aleatório, mas podemos encontrá-lo
        obfuscated_folder_name = None
        original_folder_name = self.test_dir.name
        
        arg_index = -1
        for i, arg in enumerate(nyuu_command):
            if ":sub" in arg:
                arg_index = i
                break
        
        self.assertNotEqual(arg_index, -1, "Não foi encontrado o argumento de renomeação para o arquivo aninhado.")

        rename_arg = nyuu_command[arg_index]
        self.assertTrue(rename_arg.startswith(f"{original_folder_name}/sub/file.txt:"))
        
        # O nome do arquivo no disco deve ser diferente
        on_disk_file = rename_arg.split(":")[1]
        self.assertFalse(on_disk_file.startswith(original_folder_name))

if __name__ == "__main__":
    unittest.main()
