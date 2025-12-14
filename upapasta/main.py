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
  --skip-rar                 Pula criação de RAR (upload da pasta diretamente)
  --skip-par                 Pula geração de paridade
  --skip-upload              Pula upload para Usenet
  --force                    Força sobrescrita de arquivos existentes
  --env-file FILE            Arquivo .env para credenciais (padrão: ~/.config/upapasta/.env)
  --keep-files               Mantém arquivos RAR e PAR2 após upload

Retornos:
  0: sucesso
  1: erro ao criar RAR
  2: erro ao gerar paridade
  3: erro ao fazer upload
"""

import argparse
import getpass
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .makerar import make_rar
from .makepar import make_parity, obfuscate_and_par, generate_random_name
from .upfolder import upload_to_usenet


def load_env_file(env_path: str = ".env") -> dict:
    """Carrega variáveis de ambiente de um arquivo .env simples."""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        env_vars[key.strip()] = val.strip()
    return env_vars


def prompt_for_credentials(env_file: str) -> dict:
    """Solicita credenciais ao usuário e salva no arquivo .env."""
    print("🔑 Credenciais de Usenet não encontradas ou incompletas.")
    print("Por favor, forneça as seguintes informações:")
    
    creds = {
        "NNTP_HOST": input("   - Servidor NNTP (ex: news.example.com): "),
        "NNTP_PORT": input("   - Porta NNTP (ex: 563): "),
        "NNTP_USER": input("   - Usuário NNTP: "),
        "NNTP_PASS": getpass.getpass("   - Senha NNTP: "),
        "USENET_GROUP": input("   - Grupo Usenet (ex: alt.binaries.test): "),
    }
    
    # Adiciona valores padrão para outros campos importantes
    creds["NNTP_SSL"] = "true"
    creds["NNTP_CONNECTIONS"] = "50"
    creds["ARTICLE_SIZE"] = "700K"

    # Cria o diretório se não existir
    os.makedirs(os.path.dirname(env_file), exist_ok=True)

    with open(env_file, "w") as f:
        f.write("# Configuração de credenciais para upload em Usenet com nyuu\n")
        for key, value in creds.items():
            f.write(f"{key}={value}\n")
    
    print(f"\n✅ Credenciais salvas em '{env_file}'.")
    return creds


def check_or_prompt_credentials(env_file: str) -> dict:
    """Verifica se as credenciais existem e estão preenchidas, senão, solicita."""
    required_keys = ["NNTP_HOST", "NNTP_PORT", "NNTP_USER", "NNTP_PASS", "USENET_GROUP"]
    env_vars = load_env_file(env_file)
    
    # Verifica se todas as chaves obrigatórias existem e não estão vazias
    missing_or_empty_keys = [
        key for key in required_keys if not env_vars.get(key)
    ]
    
    # Verifica se os valores padrão do .env.example não foram alterados
    is_default_host = env_vars.get("NNTP_HOST") == "news.example.com"
    is_default_user = env_vars.get("NNTP_USER") == "seu_usuario"

    if missing_or_empty_keys or is_default_host or is_default_user:
        return prompt_for_credentials(env_file)
    
    print("✅ Credenciais de Usenet carregadas.")
    return env_vars


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
        input_path: str,
        dry_run: bool = False,
        redundancy: int | None = None,
        post_size: str | None = None,
        subject: str | None = None,
        group: str | None = None,
        skip_rar: bool = False,
        skip_par: bool = False,
        skip_upload: bool = False,
        force: bool = False,
        env_file: str = ".env",
        keep_files: bool = False,
        backend: str = "parpar",
        rar_threads: int | None = None,
        par_threads: int | None = None,
        par_profile: str = "balanced",
        nzb_conflict: str | None = None,
        obfuscate: bool = False,
    ):
        self.input_path = Path(input_path).absolute()
        self.dry_run = dry_run
        self.redundancy = redundancy  # None = usar padrão do perfil
        self.post_size = post_size  # None = usar padrão do perfil
        self.subject = subject or self.input_path.name
        self.group = group
        self.skip_rar = skip_rar
        self.skip_par = skip_par
        self.skip_upload = skip_upload
        self.force = force
        self.env_file = env_file
        self.keep_files = keep_files
        self.backend = backend
        self.rar_threads = rar_threads if rar_threads is not None else (os.cpu_count() or 4)
        self.par_threads = par_threads if par_threads is not None else (os.cpu_count() or 4)
        self.par_profile = par_profile
        self.nzb_conflict = nzb_conflict
        self.obfuscate = obfuscate
        self.rar_file: str | None = None
        self.par_file: str | None = None
        # input_target is the path used for subsequent steps (string): either
        # the original folder/file or the rar file created for upload.
        self.input_target: str | None = None
        self.env_vars: dict = {}

    def validate(self) -> bool:
        """Valida entrada e ambiente."""
        if not self.input_path.exists():
            print(f"Erro: arquivo ou pasta '{self.input_path}' não existe.")
            return False

        # We allow either directories (old behaviour) or a single file
        if not self.input_path.is_dir() and not self.input_path.is_file():
            print(f"Erro: '{self.input_path}' não é um arquivo nem um diretório.")
            return False

        return True

    def run_makerar(self) -> bool:
        """Executa makerar.py."""
        # If the input is a file, default to skip RAR (do not create a RAR). The
        # caller can override via --skip-rar but the default is convenient for
        # single-file uploads that should not be repackaged into a RAR.
        if self.input_path.is_file():
            self.skip_rar = True
            print(f"✅ Single-file upload detected: {self.input_path.name} (skip RAR by default)")

        if self.skip_rar:
            # Modo upload sem RAR: use the path directly
            self.rar_file = None
            self.input_target = str(self.input_path)
            if self.input_path.is_dir():
                print(f"✅ Modo upload de pasta: {self.input_path.name}")
            else:
                print(f"✅ Modo upload de arquivo: {self.input_path.name}")
            # return True, but don't set rar_file
            return True

        print("\n" + "=" * 60)
        print("📦 ETAPA 1: Criar arquivo RAR")
        print("=" * 60)

        if self.dry_run:
            print(f"[DRY-RUN] pularia a criação do RAR.")
            self.rar_file = str(self.input_path.parent / f"{self.input_path.name}.rar")
            self.input_target = self.rar_file
            print(f"[DRY-RUN] RAR seria criado em: {self.rar_file}")
            return True

        print(f"📥 Compactando {self.input_path.name}...")
        print("-" * 60)

        try:
            rc = make_rar(str(self.input_path), self.force, threads=self.rar_threads)
            if rc == 0:
                print("-" * 60)
                self.rar_file = str(self.input_path.parent / f"{self.input_path.name}.rar")
                self.input_target = self.rar_file
                if os.path.exists(self.rar_file):
                    return True
                else:
                    print("❌ Erro: Arquivo RAR não foi encontrado após a execução bem-sucedida.")
                    return False
            else:
                print("-" * 60)
                print(f"\n❌ Erro ao criar RAR. Veja o output acima para detalhes. (rc={rc})")
                return False
        except Exception as e:
            print(f"❌ Erro inesperado ao executar make_rar: {e}")
            return False

    def run_makepar(self) -> bool:
        """Executa makepar.py."""
        if not self.input_target:
            print("Erro: caminho de entrada não definido.")
            return False

        if self.skip_par:
            # Procura arquivo .par2 existente
            if os.path.isdir(self.input_target):
                par_path = os.path.join(os.path.dirname(self.input_target), os.path.basename(self.input_target) + ".par2")
            else:
                par_path = os.path.splitext(self.input_target)[0] + ".par2"
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

        if self.dry_run:
            print(f"[DRY-RUN] pularia a criação do PAR2.")
            if os.path.isdir(self.input_target):
                self.par_file = os.path.join(os.path.dirname(self.input_target), os.path.basename(self.input_target) + ".par2")
            else:
                self.par_file = os.path.splitext(self.input_target)[0] + ".par2"
            print(f"[DRY-RUN] PAR2 será criado em: {self.par_file}")
            return True

        if self.obfuscate:
            print("🔐 Gerando paridade com ofuscação no subject...")
            print("-" * 60)

            try:
                rc = make_parity(
                    self.input_target,
                    redundancy=self.redundancy,
                    force=True,  # Sempre forçar para ofuscação, pois subject muda
                    backend=self.backend,
                    usenet=True,
                    post_size=self.post_size,
                    threads=self.par_threads,
                    profile=self.par_profile,
                )
            except Exception as e:
                print(f"Erro ao executar make_parity: {e}")
                return False

            if rc != 0:
                print("-" * 60)
                print(f"\n❌ Erro ao gerar paridade (código {rc}).")
                return False

            print("-" * 60)
            # Ofuscar apenas o subject
            base_name = os.path.basename(self.input_target)
            if self.input_path.is_file():
                name, ext = os.path.splitext(base_name)
                obfuscated_subject = generate_random_name() + ext
            else:
                obfuscated_subject = generate_random_name()
            self.subject = obfuscated_subject
            print(f"✨ Subject da postagem atualizado para nome ofuscado: {self.subject}")
            # O nome do arquivo par2 é baseado no nome original
            self.par_file = os.path.splitext(self.input_target)[0] + ".par2"
            if os.path.exists(self.par_file):
                return True
            else:
                print("❌ Erro: Arquivo de paridade não foi encontrado.")
                return False
        else:
            print(f"🔐 Gerando paridade (perfil: {self.par_profile})...")
            print("-" * 60)

            try:
                rc = make_parity(
                    self.input_target,
                    redundancy=self.redundancy,
                    force=self.force,
                    backend=self.backend,
                    usenet=True,
                    post_size=self.post_size,
                    threads=self.par_threads,
                    profile=self.par_profile,
                )
            except Exception as e:
                print(f"Erro ao executar make_parity: {e}")
                return False

            if rc != 0:
                print("-" * 60)
                print(f"\n❌ Erro ao gerar paridade (código {rc}).")
                return False

            print("-" * 60)
            # O nome do arquivo par2 é baseado no nome original
            self.par_file = os.path.splitext(self.input_target)[0] + ".par2"
            return True

    def run_upload(self) -> bool:
        """Executa upfolder.py, permitindo que a barra de progresso nativa apareça."""
        if not self.input_target:
            print("Erro: caminho de entrada não definido.")
            return False
        
        if self.dry_run:
            print("DRY-RUN: Pularia o upload.")
            return True

        print("\n" + "=" * 60)
        print("📤 ETAPA 3: Upload para Usenet")
        print("=" * 60)

        if self.dry_run:
            print(f"[DRY-RUN] pularia o upload.")
            return True

        try:
            # If a nzb_conflict mode was given via CLI, inject it into env_vars so
            # upload_to_usenet can read it. Otherwise, the env_vars may already
            # contain NZB_CONFLICT from the .env file.
            if self.nzb_conflict:
                self.env_vars['NZB_CONFLICT'] = self.nzb_conflict

            rc = upload_to_usenet(
                self.input_target,
                env_vars=self.env_vars,
                dry_run=self.dry_run,
                subject=self.subject,
                group=self.group,
                skip_rar=self.skip_rar,
            )
            return rc == 0
        except Exception as e:
            print(f"\n❌ Erro ao executar upload_to_usenet: {e}")
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
        elif self.par_file:
            # Para --skip-rar, usar o nome base do arquivo PAR2
            base_name = os.path.splitext(self.par_file)[0]
        else:
            base_name = None

        if base_name:
            import glob
            # Usar glob.escape para lidar com caracteres especiais (como [, ])
            par_volumes = glob.glob(glob.escape(base_name) + ".vol*.par2")
            files_to_delete.extend(par_volumes)

        # Deletar arquivos
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"  ✓ Removido diretório: {os.path.basename(file_path)}")
                    else:
                        os.remove(file_path)
                        print(f"  ✓ Removido: {os.path.basename(file_path)}")
                    deleted_count += 1
            except Exception as e:
                print(f"  ✗ Erro ao remover {file_path}: {e}")

        if deleted_count > 0:
            print(f"\n✅ {deleted_count} arquivo(s) removido(s) com sucesso")
        print()

    def _cleanup_on_error(self) -> None:
        """Limpa arquivos temporários criados quando há erro/falha."""
        print("\n🧹 Limpando arquivos temporários devido a erro...")

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
        elif self.par_file:
            # Para --skip-rar, usar o nome base do arquivo PAR2
            base_name = os.path.splitext(self.par_file)[0]
        else:
            base_name = None

        if base_name:
            import glob
            # Usar glob.escape para lidar com caracteres especiais (como [, ])
            par_volumes = glob.glob(glob.escape(base_name) + ".vol*.par2")
            files_to_delete.extend(par_volumes)

        # Deletar arquivos
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"  ✓ Removido diretório: {os.path.basename(file_path)}")
                    else:
                        os.remove(file_path)
                        print(f"  ✓ Removido: {os.path.basename(file_path)}")
                    deleted_count += 1
            except Exception as e:
                print(f"  ✗ Erro ao remover {file_path}: {e}")

        if deleted_count > 0:
            print(f"\n✅ {deleted_count} arquivo(s) removido(s) com sucesso")
        print()

    def check_nzb_conflict_early(self) -> bool:
        """Verifica conflito de NZB antecipadamente, antes de qualquer processamento."""
        if self.skip_upload or self.dry_run:
            return True  # Não há upload, então não há conflito

        # Determinar o caminho do NZB que seria criado
        from .upfolder import upload_to_usenet
        import tempfile
        import os

        # Simular a lógica de upload_to_usenet para determinar o nzb_out
        input_path = str(self.input_target) if self.input_target else str(self.input_path)
        is_folder = os.path.isdir(input_path)

        # Usar a mesma lógica de template do upfolder.py
        env_vars = self.env_vars.copy()
        if self.nzb_conflict:
            env_vars['NZB_CONFLICT'] = self.nzb_conflict

        nzb_out_template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT")
        if not nzb_out_template:
            if is_folder and not self.skip_rar:
                nzb_out_template = "{filename}_content.nzb"
            else:
                nzb_out_template = "{filename}.nzb"

        # Determinar o basename
        basename = os.path.basename(input_path)
        if not is_folder:
            basename = os.path.splitext(basename)[0]
        nzb_filename = nzb_out_template.replace("{filename}", basename)

        # Determinar o diretório de saída do NZB
        nzb_dir = env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
        nzb_out_abs = os.path.join(nzb_dir, nzb_filename)

        # Verificar conflito
        nzb_conflict = env_vars.get("NZB_CONFLICT") or os.environ.get("NZB_CONFLICT") or "rename"

        if os.path.exists(nzb_out_abs):
            if nzb_conflict == "fail":
                print(f"Erro: arquivo NZB já existe: {nzb_out_abs}. Parando por configuração 'fail'.")
                return False
            elif nzb_conflict == "overwrite":
                print(f"Aviso: arquivo NZB já existe: {nzb_out_abs} - será sobrescrito.")
            else:  # rename
                base, ext = os.path.splitext(nzb_out_abs)
                counter = 1
                while True:
                    candidate = f"{base}-{counter}{ext}"
                    if not os.path.exists(candidate):
                        break
                    counter += 1
                print(f"Aviso: arquivo NZB já existe: {nzb_out_abs} - será usado: {os.path.basename(candidate)}")

        return True

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
        
        # DEBUG: Original input_path
        print(f"DEBUG: UpaPastaOrchestrator.run() - Original input_path: {self.input_path}")
        
        # Carrega e valida as credenciais se o upload não for pulado
        if not self.skip_upload:
            self.env_vars = check_or_prompt_credentials(self.env_file)
            if not self.env_vars:
                return 3  # Erro na obtenção de credenciais

        print("\n" + "=" * 60)
        print("🚀 UpaPasta — Workflow Completo de Upload para Usenet")
        print("=" * 60)
        print(f"📁 Entrada:      {self.input_path.name}")
        print(f"🎯 Perfil PAR2: {self.par_profile}")
        print(f"📊 Post-size:  {self.post_size or '(do perfil)'}")
        print(f"✉️  Subject:    {self.subject}")
        print(f"⚡ Threads RAR: {self.rar_threads}")
        print(f"⚡ Threads PAR: {self.par_threads}")
        if self.dry_run:
            print("⚠️  [DRY-RUN] Nenhum arquivo será criado ou enviado")
        print()

        # Valida ambiente
        if not self.validate():
            return 1

        # Verificar conflito de NZB antecipadamente (antes de qualquer processamento)
        if not self.check_nzb_conflict_early():
            return 3  # Mesmo código de erro do upload

        # Etapa 1: Criar RAR
        if not self.skip_rar:
            step_start_time = time.time()
            if not self.run_makerar():
                self._cleanup_on_error()
                return 1
            timings["rar"] = time.time() - step_start_time
        else:
            if not self.run_makerar():  # tenta pular, mas valida existência
                self._cleanup_on_error()
                return 1

        # Etapa 2: Gerar paridade
        if not self.skip_par:
            step_start_time = time.time()
            if not self.run_makepar():
                self._cleanup_on_error()
                return 2
            timings["par"] = time.time() - step_start_time
        else:
            if not self.run_makepar():  # tenta pular, mas valida existência
                self._cleanup_on_error()
                return 2

        # Coletar informações dos arquivos ANTES do upload/cleanup
        if self.input_target:
            if os.path.isdir(self.input_target):
                # Calcular tamanho total da pasta
                total_size_bytes = 0
                for root, dirs, files in os.walk(self.input_target):
                    for file in files:
                        total_size_bytes += os.path.getsize(os.path.join(root, file))
                stats["rar_size_mb"] = total_size_bytes / (1024 * 1024)
                base_name = self.input_target
            else:
                stats["rar_size_mb"] = os.path.getsize(self.input_target) / (1024 * 1024)
                base_name = os.path.splitext(self.input_target)[0]
            
            import glob
            par_volumes = glob.glob(glob.escape(base_name) + "*.par2")
            stats["par2_file_count"] = len(par_volumes)
            total_par_size_bytes = sum(os.path.getsize(f) for f in par_volumes)
            stats["par2_size_mb"] = total_par_size_bytes / (1024 * 1024)

        # Etapa 3: Upload
        if not self.skip_upload:
            step_start_time = time.time()
            if not self.run_upload():
                self._cleanup_on_error()
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
        print(f"  » Entrada de Origem: {self.input_path.name}")
        if not self.skip_upload:
            # Mostra o grupo do argumento, ou do .env, ou um fallback
            group_from_env = self.env_vars.get("USENET_GROUP")
            display_group = self.group or group_from_env or "(Não especificado)"
            print(f"  » Subject da Postagem: {self.subject}")
            print(f"  » Grupo Usenet: {display_group}")

        print("\n⏱️ ESTATÍSTICAS DE TEMPO:")
        print("-" * 25)
        if not self.skip_rar:
            print(f"  » Tempo para criar RAR:    {format_time(int(timings['rar']))}")
        print(f"  » Tempo para gerar PAR2:   {format_time(int(timings['par']))}")
        if not self.skip_upload:
            print(f"  » Tempo de Upload:         {format_time(int(timings['upload']))}")
        print("-" * 25)
        print(f"  » Tempo Total:             {format_time(int(timings['total']))}")

        print("\n📦 ARQUIVOS GERADOS:")
        print("-" * 25)
        if stats["rar_size_mb"] > 0:
            if self.rar_file and os.path.exists(self.rar_file):
                print(f"  » Arquivo RAR: {os.path.basename(self.rar_file)} ({stats['rar_size_mb']:.2f} MB)")
            elif os.path.isdir(self.input_path):
                print(f"  » Arquivos da pasta: {os.path.basename(self.input_path)} ({stats['rar_size_mb']:.2f} MB)")
            else:
                print(f"  » Arquivo: {os.path.basename(self.input_path)} ({stats['rar_size_mb']:.2f} MB)")
        
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
    p.add_argument("input", help="Arquivo ou pasta a fazer upload")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem executar",
    )
    p.add_argument(
        "--par-profile",
        choices=("fast", "balanced", "safe"),
        default="balanced",
        help="Perfil de otimização PAR2 (padrão: balanced)",
    )
    p.add_argument(
        "-r", "--redundancy",
        type=int,
        default=None,
        help="Redundância PAR2 em porcentagem (sobrescreve perfil)",
    )
    p.add_argument(
        "--backend",
        choices=("parpar", "par2"),
        default="parpar",
        help="Backend para geração PAR2 (padrão: parpar)",
    )
    p.add_argument(
        "--post-size",
        default=None,
        help="Tamanho alvo de post Usenet (sobrescreve perfil)",
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
        default=os.path.expanduser("~/.config/upapasta/.env"),
        help="Arquivo .env para credenciais (padrão: ~/.config/upapasta/.env)",
    )
    p.add_argument(
        "--keep-files",
        action="store_true",
        help="Mantém arquivos RAR e PAR2 após upload",
    )
    p.add_argument(
        "--rar-threads",
        type=int,
        default=None,
        help="Número de threads para criação de RAR (padrão: número de CPUs disponíveis)",
    )
    p.add_argument(
        "--par-threads",
        type=int,
        default=None,
        help="Número de threads para geração de PAR2 (padrão: número de CPUs disponíveis)",
    )
    p.add_argument(
        "--nzb-conflict",
        choices=("rename", "overwrite", "fail"),
        default=None,
        help="Como tratar conflitos quando o .nzb já existe na pasta de destino (default: Env or 'rename')",
    )
    p.add_argument(
        "--obfuscate",
        action="store_true",
        help="Ofusca o nome do arquivo antes de gerar o PAR2 e fazer o upload.",
    )
    return p.parse_args()


def check_dependencies(needs_rar: bool = True):
    """Verifica se as dependências de linha de comando (rar, nyuu, parpar) estão instaladas."""
    print("🔍 Verificando dependências...")
    required_commands = ["nyuu", "parpar"]
    if needs_rar:
        required_commands.insert(0, "rar")
    missing_commands = []

    for cmd in required_commands:
        if not shutil.which(cmd):
            missing_commands.append(cmd)

    if missing_commands:
        print("❌ Dependências não encontradas:")
        for cmd in missing_commands:
            print(f"  - '{cmd}' não está instalado ou não está no PATH.")
        print("\n   Por favor, instale as dependências e tente novamente.")
        print("   Você pode encontrar instruções de instalação em INSTALL.md")
        return False

    print("✅ Todas as dependências foram encontradas.")
    return True


def main():
    args = parse_args()

    # Determine whether rar is needed: rar not needed for single-file uploads
    # when skip_rar is expected. If input is a file and user didn't explicitly
    # disable skip-rar, then rar is not required.
    needs_rar = True
    try:
        from pathlib import Path
        p = Path(args.input)
        if p.exists() and p.is_file():
            needs_rar = False
    except Exception:
        pass

    if not check_dependencies(needs_rar):
        sys.exit(1)

    orchestrator = UpaPastaOrchestrator(
        input_path=args.input,
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
        rar_threads=args.rar_threads,
        par_threads=args.par_threads,
        par_profile=args.par_profile,
        nzb_conflict=args.nzb_conflict,
        obfuscate=args.obfuscate,
    )

    rc = orchestrator.run()
    sys.exit(rc)


if __name__ == "__main__":
    main()
