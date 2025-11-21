#!/usr/bin/env python3
"""
main.py

Script orchestrador para fazer upload de uma pasta na Usenet.

Workflow completo:
  1. Recebe uma pasta
  2. Cria arquivo .rar (makerar.py)
  3. Gera paridade .par2 (makepar.py)
  4. Faz upload para Usenet (upfolder.py)

Mostra barra de progresso para cada etapa e durante o upload.

Uso:
  python3 main.py /caminho/para/pasta

Opções:
  --dry-run                  Mostra o que seria feito sem executar
  --redundancy PERCENT       Redundância PAR2 (padrão: 15)
  --backend BACKEND          Backend para geração PAR2 (padrão: parpar)
  --post-size SIZE           Tamanho alvo de post (padrão: 20M)
  --subject SUBJECT          Subject da postagem (padrão: nome da pasta)
  --group GROUP              Newsgroup (padrão: do .env)
  --skip-rar                 Pula criação de RAR (assume arquivo existe)
  --skip-par                 Pula geração de paridade
  --skip-upload              Pula upload para Usenet
  --force                    Força sobrescrita de arquivos existentes
  --env-file FILE            Arquivo .env para credenciais
  --keep-files               Mantém arquivos RAR e PAR2 após upload

Retornos:
  0: sucesso
  1: erro ao criar RAR
  2: erro ao gerar paridade
  3: erro ao fazer upload
"""

import argparse
import os
import re
import subprocess
import sys
import time
import pty
from pathlib import Path


def run_command_with_pty(cmd: list[str]) -> None:
    """Executa um comando em um pseudo-terminal para preservar o output formatado."""
    master, slave = pty.openpty()
    
    # Inicia o processo
    process = subprocess.Popen(cmd, stdout=slave, stderr=slave, close_fds=True)
    
    # Fecha o descritor do slave no processo pai
    os.close(slave)
    
    # Lê o output do master
    try:
        while True:
            try:
                # Lê até 1024 bytes do processo filho
                data = os.read(master, 1024)
            except OSError:
                # OSError (por ex, EIO) significa que o processo filho terminou
                break
            
            if not data:
                break
                
            # Escreve o output para o stdout do terminal atual
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            
    finally:
        # Fecha o master
        os.close(master)
        
        # Espera o processo terminar e verifica o código de retorno
        ret_code = process.wait()
        if ret_code != 0:
            # Levanta um erro se o comando falhou
            raise subprocess.CalledProcessError(ret_code, cmd)


def format_time(seconds: int) -> str:
    """Formata segundos como HH:MM:SS."""
    if seconds < 0:
        return "00:00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class UpaPastaOrchestrator:
    """Orquestra o workflow completo de upload para Usenet."""

    def __init__(
        self,
        folder_path: str,
        dry_run: bool = False,
        redundancy: int = 15,
        post_size: str = "20M",
        subject: str | None = None,
        group: str | None = None,
        skip_rar: bool = False,
        skip_par: bool = False,
        skip_upload: bool = False,
        force: bool = False,
        env_file: str = ".env",
        keep_files: bool = False,
        backend: str = "parpar",
    ):
        self.folder_path = Path(folder_path).absolute()
        self.dry_run = dry_run
        self.redundancy = redundancy
        self.post_size = post_size
        self.subject = subject or self.folder_path.name
        self.group = group
        self.skip_rar = skip_rar
        self.skip_par = skip_par
        self.skip_upload = skip_upload
        self.force = force
        self.env_file = env_file
        self.keep_files = keep_files
        self.backend = backend
        self.rar_file: str | None = None
        self.par_file: str | None = None

    def validate(self) -> bool:
        """Valida entrada e ambiente."""
        if not self.folder_path.exists():
            print(f"Erro: pasta '{self.folder_path}' não existe.")
            return False

        if not self.folder_path.is_dir():
            print(f"Erro: '{self.folder_path}' não é um diretório.")
            return False

        if not self.skip_upload and not os.path.exists(self.env_file):
            print("Erro: arquivo .env não encontrado. Copie .env.example para .env e configure.")
            return False

        return True

    def run_makerar(self) -> bool:
        """Executa makerar.py."""
        if self.skip_rar:
            # Procura arquivo .rar existente
            parent = self.folder_path.parent
            potential_rar = parent / f"{self.folder_path.name}.rar"
            if potential_rar.exists():
                self.rar_file = str(potential_rar)
                size_mb = os.path.getsize(self.rar_file) / (1024 * 1024)
                print(f"✅ Usando RAR existente: {size_mb:.2f} MB")
                return True
            else:
                print(f"❌ Erro: --skip-rar mas arquivo {potential_rar} não existe.")
                return False

        print("\n" + "=" * 60)
        print("📦 ETAPA 1: Criar arquivo RAR")
        print("=" * 60)

        cmd = [
            "python3",
            "makerar.py",
            str(self.folder_path),
        ]
        if self.force:
            cmd.append("-f")

        if self.dry_run:
            print(f"[DRY-RUN] Comando: {' '.join(cmd)}")
            self.rar_file = str(self.folder_path.parent / f"{self.folder_path.name}.rar")
            print(f"[DRY-RUN] RAR será criado em: {self.rar_file}")
            return True

        print(f"📥 Compactando {self.folder_path.name}...")
        print("-" * 60)

        try:
            run_command_with_pty(cmd)
            print("-" * 60)
            self.rar_file = str(self.folder_path.parent / f"{self.folder_path.name}.rar")
            if os.path.exists(self.rar_file):
                return True
            else:
                print("❌ Erro: Arquivo RAR não foi encontrado após a execução bem-sucedida.")
                return False
        except subprocess.CalledProcessError:
            print("-" * 60)
            print("\n❌ Erro ao criar RAR. Veja o output acima para detalhes.")
            return False
        except Exception as e:
            print(f"❌ Erro inesperado ao executar makerar.py: {e}")
            return False

    def run_makepar(self) -> bool:
        """Executa makepar.py."""
        if not self.rar_file:
            print("Erro: arquivo RAR não definido.")
            return False

        if self.skip_par:
            # Procura arquivo .par2 existente
            par_path = os.path.splitext(self.rar_file)[0] + ".par2"
            if os.path.exists(par_path):
                self.par_file = par_path
                size_mb = os.path.getsize(self.par_file) / (1024 * 1024)
                print(f"✅ Usando paridade existente: {size_mb:.2f} MB")
                return True
            else:
                print(f"❌ Erro: --skip-par mas arquivo {par_path} não existe.")
                return False

        print("\n" + "=" * 60)
        print("🛡️  ETAPA 2: Gerar arquivo de paridade PAR2")
        print("=" * 60)

        cmd = [
            "python3",
            "makepar.py",
            "-r", str(self.redundancy),
            "--usenet",
            "--post-size", self.post_size,
            "--backend", self.backend,
            str(self.rar_file),
        ]
        if self.force:
            cmd.append("--force")

        if self.dry_run:
            print(f"[DRY-RUN] Comando: {' '.join(cmd)}")
            self.par_file = os.path.splitext(self.rar_file)[0] + ".par2"
            print(f"[DRY-RUN] PAR2 será criado em: {self.par_file}")
            return True

        print(f"🔐 Gerando paridade com {self.redundancy}% de redundância...")
        print("-" * 60)

        try:
            run_command_with_pty(cmd)
            print("-" * 60)
            self.par_file = os.path.splitext(self.rar_file)[0] + ".par2"
            if os.path.exists(self.par_file):
                return True
            else:
                print("❌ Erro: Arquivo de paridade não foi encontrado após a execução bem-sucedida.")
                return False
        except subprocess.CalledProcessError:
            print("-" * 60)
            print("\n❌ Erro ao gerar paridade. Veja o output acima para detalhes.")
            return False
        except Exception as e:
            print(f"❌ Erro inesperado ao executar makepar.py: {e}")
            return False

    def run_upload(self) -> bool:
        """Executa upfolder.py, permitindo que a barra de progresso nativa apareça."""
        if not self.rar_file:
            print("Erro: arquivo RAR não definido.")
            return False
        
        if self.dry_run:
            print("DRY-RUN: Pularia o upload.")
            return True

        print("\n" + "=" * 60)
        print("📤 ETAPA 3: Upload para Usenet")
        print("=" * 60)

        cmd = [
            "python3",
            "upfolder.py",
            str(self.rar_file),
            "--subject", self.subject,
            "--env-file", self.env_file,
        ]
        if self.group:
            cmd.extend(["--group", self.group])
        
        if self.dry_run:
            cmd.append("--dry-run")
            print(f"[DRY-RUN] Comando: {' '.join(cmd)}")
            return True

        try:
            # Executar upfolder.py e deixar que ele mostre o output do nyuu
            run_command_with_pty(cmd)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Erro: upfolder.py retornou código {e.returncode}.")
            return False
        except Exception as e:
            print(f"\n❌ Erro ao executar upfolder.py: {e}")
            return False

    def cleanup(self) -> None:
        """Remove arquivos RAR e PAR2 após upload bem-sucedido."""
        if self.keep_files:
            print("\n⚡ [--keep-files] Mantendo arquivos RAR e PAR2.")
            return

        print("\n🧹 Limpando arquivos temporários...")

        files_to_delete = []
        
        # Arquivo RAR
        if self.rar_file and os.path.exists(self.rar_file):
            files_to_delete.append(self.rar_file)

        # Arquivo PAR2 base
        if self.par_file and os.path.exists(self.par_file):
            files_to_delete.append(self.par_file)

        # Arquivos de volume PAR2 (.vol00+01.par2, .vol01+02.par2, etc.)
        if self.rar_file:
            base_name = os.path.splitext(self.rar_file)[0]
            import glob
            # Usar glob.escape para lidar com caracteres especiais (como [, ])
            par_volumes = glob.glob(glob.escape(base_name) + ".vol*.par2")
            files_to_delete.extend(par_volumes)

        # Deletar arquivos
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"  ✓ Removido: {os.path.basename(file_path)}")
                    deleted_count += 1
            except Exception as e:
                print(f"  ✗ Erro ao remover {file_path}: {e}")

        if deleted_count > 0:
            print(f"\n✅ {deleted_count} arquivo(s) removido(s) com sucesso")
        print()

    def run(self) -> int:
        """Executa o workflow completo."""
        
        # --- Timers e stats ---
        timings = {
            "total": 0.0, "rar": 0.0, "par": 0.0, "upload": 0.0
        }
        stats = {
            "rar_size_mb": 0.0, "par2_size_mb": 0.0, "par2_file_count": 0
        }
        total_start_time = time.time()
        
        # Tenta carregar o grupo do .env para mostrar no sumário
        try:
            env_vars = load_env_file(self.env_file)
            group_from_env = env_vars.get("USENET_GROUP")
        except Exception:
            group_from_env = None

        print("\n" + "=" * 60)
        print("🚀 UpaPasta — Workflow Completo de Upload para Usenet")
        print("=" * 60)
        print(f"📁 Pasta:      {self.folder_path.name}")
        print(f"🛡️  Redundância: {self.redundancy}%")
        print(f"📊 Post-size:  {self.post_size}")
        print(f"✉️  Subject:    {self.subject}")
        if self.dry_run:
            print("⚠️  [DRY-RUN] Nenhum arquivo será criado ou enviado")
        print()

        # Valida ambiente
        if not self.validate():
            return 1

        # Etapa 1: Criar RAR
        if not self.skip_rar:
            step_start_time = time.time()
            if not self.run_makerar():
                return 1
            timings["rar"] = time.time() - step_start_time
        else:
            if not self.run_makerar():  # tenta pular, mas valida existência
                return 1

        # Etapa 2: Gerar paridade
        if not self.skip_par:
            step_start_time = time.time()
            if not self.run_makepar():
                return 2
            timings["par"] = time.time() - step_start_time
        else:
            if not self.run_makepar():  # tenta pular, mas valida existência
                return 2

        # Coletar informações dos arquivos ANTES do upload/cleanup
        if self.rar_file and os.path.exists(self.rar_file):
            stats["rar_size_mb"] = os.path.getsize(self.rar_file) / (1024 * 1024)
            
            base_name = os.path.splitext(self.rar_file)[0]
            import glob
            par_volumes = glob.glob(glob.escape(base_name) + "*.par2")
            stats["par2_file_count"] = len(par_volumes)
            total_par_size_bytes = sum(os.path.getsize(f) for f in par_volumes)
            stats["par2_size_mb"] = total_par_size_bytes / (1024 * 1024)

        # Etapa 3: Upload
        if not self.skip_upload:
            step_start_time = time.time()
            if not self.run_upload():
                return 3
            timings["upload"] = time.time() - step_start_time
            # Limpar arquivos após upload bem-sucedido
            self.cleanup()
        else:
            print("\n⏭️  [--skip-upload] Upload foi pulado.")

        timings["total"] = time.time() - total_start_time
        
        # --- SUMÁRIO FINAL ---
        print("\n\n" + "=" * 60)
        print("🎉 WORKFLOW CONCLUÍDO COM SUCESSO 🎉")
        print("=" * 60)
        
        print("\n📊 RESUMO DA OPERAÇÃO:")
        print("-" * 25)
        print(f"  » Pasta de Origem: {self.folder_path.name}")
        if not self.skip_upload:
            # Mostra o grupo do argumento, ou do .env, ou um fallback
            display_group = self.group or group_from_env or "(Não especificado)"
            print(f"  » Subject da Postagem: {self.subject}")
            print(f"  » Grupo Usenet: {display_group}")

        print("\n⏱️ ESTATÍSTICAS DE TEMPO:")
        print("-" * 25)
        print(f"  » Tempo para criar RAR:    {format_time(int(timings['rar']))}")
        print(f"  » Tempo para gerar PAR2:   {format_time(int(timings['par']))}")
        if not self.skip_upload:
            print(f"  » Tempo de Upload:         {format_time(int(timings['upload']))}")
        print("-" * 25)
        print(f"  » Tempo Total:             {format_time(int(timings['total']))}")

        print("\n📦 ARQUIVOS GERADOS:")
        print("-" * 25)
        if stats["rar_size_mb"] > 0:
            print(f"  » Arquivo RAR: {os.path.basename(self.rar_file)} ({stats['rar_size_mb']:.2f} MB)")
        
        if stats["par2_file_count"] > 0:
            print(f"  » Arquivos PAR2: {stats['par2_file_count']} arquivos ({stats['par2_size_mb']:.2f} MB)")

        print("-" * 25)
        total_size = stats['rar_size_mb'] + stats['par2_size_mb']
        print(f"  » Tamanho Total: {total_size:.2f} MB")

        print("\n" + "=" * 60 + "\n")

        return 0


def parse_args():
    p = argparse.ArgumentParser(
        description="UpaPasta — Upload de pasta para Usenet com RAR + PAR2",
        epilog="Exemplo: python3 main.py /caminho/para/pasta",
    )
    p.add_argument("folder", help="Pasta a fazer upload")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem executar",
    )
    p.add_argument(
        "-r", "--redundancy",
        type=int,
        default=15,
        help="Redundância PAR2 em porcentagem (padrão: 15)",
    )
    p.add_argument(
        "--backend",
        choices=("parpar", "par2"),
        default="parpar",
        help="Backend para geração PAR2 (padrão: parpar)",
    )
    p.add_argument(
        "--post-size",
        default="20M",
        help="Tamanho alvo de post Usenet (padrão: 20M)",
    )
    p.add_argument(
        "-s", "--subject",
        default=None,
        help="Subject da postagem (padrão: nome da pasta)",
    )
    p.add_argument(
        "-g", "--group",
        default=None,
        help="Newsgroup (padrão: do .env)",
    )
    p.add_argument(
        "--skip-rar",
        action="store_true",
        help="Pula criação de RAR (assume arquivo existe)",
    )
    p.add_argument(
        "--skip-par",
        action="store_true",
        help="Pula geração de paridade",
    )
    p.add_argument(
        "--skip-upload",
        action="store_true",
        help="Pula upload para Usenet",
    )
    p.add_argument(
        "-f", "--force",
        action="store_true",
        help="Força sobrescrita de arquivos existentes",
    )
    p.add_argument(
        "--env-file",
        default=".env",
        help="Arquivo .env para credenciais (padrão: .env)",
    )
    p.add_argument(
        "--keep-files",
        action="store_true",
        help="Mantém arquivos RAR e PAR2 após upload",
    )
    return p.parse_args()


def main():
    args = parse_args()

    orchestrator = UpaPastaOrchestrator(
        folder_path=args.folder,
        dry_run=args.dry_run,
        redundancy=args.redundancy,
        backend=args.backend,
        post_size=args.post_size,
        subject=args.subject,
        group=args.group,
        skip_rar=args.skip_rar,
        skip_par=args.skip_par,
        skip_upload=args.skip_upload,
        force=args.force,
        env_file=args.env_file,
        keep_files=args.keep_files,
    )

    rc = orchestrator.run()
    sys.exit(rc)


if __name__ == "__main__":
    main()
