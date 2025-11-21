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
from pathlib import Path

try:
    from tqdm import tqdm  # type: ignore
except ImportError:
    # Fallback se tqdm não estiver instalado
    class tqdm:  # type: ignore
        def __init__(self, iterable=None, desc="", total=None, **kwargs):
            self.iterable = iterable
            self.desc = desc
            self.total = total or (len(iterable) if iterable else 0)
            self.current = 0

        def __iter__(self):
            for item in self.iterable or []:
                self.current += 1
                if self.desc:
                    print(f"{self.desc} [{self.current}/{self.total}]")
                yield item

        def update(self, n=1):
            self.current += n
            if self.desc:
                print(f"{self.desc} [{self.current}/{self.total}]")


class UploadProgressParser:
    """Parser para extrair progresso do output nyuu."""

    def __init__(self, debug: bool = False):
        self.total_articles: int | None = None
        self.uploaded_articles = 0
        self.total_size: float | None = None
        self.uploaded_size = 0.0
        self.start_time: float | None = None
        self.lines_processed = 0
        self.debug = debug

    def parse_line(self, line: str) -> dict:
        """Parse uma linha de output nyuu e extrai informações de progresso."""
        result: dict = {
            "raw": line,
            "info": None,
            "progress": None,
            "speed": None,
            "eta": None,
        }

        # Debug: mostrar linhas que podem conter progresso
        if any(keyword in line.lower() for keyword in ["upload", "article", "file", "progress", "sent", "transfer", "sending"]):
            if self.debug:
                print(f"[DEBUG] Potential progress line: {line}")

        # Padrão 1: [INFO] Uploading X article(s) from Y file(s) totalling Z MiB
        match = re.search(
            r"Uploading (\d+) article\(s\).*?(\d+(?:\.\d+)?) MiB",
            line,
        )
        if match:
            self.total_articles = int(match.group(1))
            self.total_size = float(match.group(2))
            self.start_time = time.time()
            result["info"] = f"Total: {self.total_articles} artigos ({self.total_size:.2f} MiB)"
            if self.debug:
                print(f"[DEBUG] Pattern 1 matched: {self.total_articles} articles, {self.total_size} MiB")

        # Padrão 2: Uploaded X/Y articles, Z/W files
        match = re.search(r"Uploaded (\d+)/(\d+) articles", line)
        if match:
            self.uploaded_articles = int(match.group(1))
            total = int(match.group(2))
            if total > 0 and self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    speed_articles_per_sec = self.uploaded_articles / elapsed
                    remaining = total - self.uploaded_articles
                    eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                    result["progress"] = float(self.uploaded_articles / total)
                    result["speed"] = float(speed_articles_per_sec)
                    result["eta"] = int(eta_seconds)
                    if self.debug:
                        print(f"[DEBUG] Pattern 2 matched: {self.uploaded_articles}/{total} articles, progress: {result['progress']:.3f}")

        # Padrão 3: Progress indicators like "X/Y" or "X of Y" (articles)
        match = re.search(r"(\d+)\s*(?:/|of)\s*(\d+).*?articles?", line, re.IGNORECASE)
        if match and not result["progress"]:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                self.uploaded_articles = current
                self.total_articles = total
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        speed_articles_per_sec = current / elapsed
                        remaining = total - current
                        eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                        result["progress"] = float(current / total)
                        result["speed"] = float(speed_articles_per_sec)
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 3 matched: {current}/{total} articles, progress: {result['progress']:.3f}")

        # Padrão 4: "sending article X of Y" or "article X of Y"
        match = re.search(r"(?:sending\s+)?article\s+(\d+)\s+of\s+(\d+)", line, re.IGNORECASE)
        if match and not result["progress"]:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                self.uploaded_articles = current
                self.total_articles = total
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        speed_articles_per_sec = current / elapsed
                        remaining = total - current
                        eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                        result["progress"] = float(current / total)
                        result["speed"] = float(speed_articles_per_sec)
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 4 matched: article {current} of {total}, progress: {result['progress']:.3f}")

        # Padrão 5: "X/Y" sem contexto específico (mas com números próximos)
        match = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if match and not result["progress"] and not any(word in line.lower() for word in ["file", "files", "mb", "mib", "kb", "kib"]):
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0 and total < 10000:  # Reasonable limit for articles
                self.uploaded_articles = current
                self.total_articles = total
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        speed_articles_per_sec = current / elapsed
                        remaining = total - current
                        eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                        result["progress"] = float(current / total)
                        result["speed"] = float(speed_articles_per_sec)
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 5 matched: {current}/{total}, progress: {result['progress']:.3f}")

        # Padrão 6: Percentage indicators
        match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if match and not result["progress"]:
            percent = float(match.group(1)) / 100.0
            if 0 <= percent <= 1:
                result["progress"] = percent
                # Estimate speed and ETA if we have timing
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0 and percent > 0:
                        speed_percent_per_sec = percent / elapsed
                        remaining_percent = 1.0 - percent
                        eta_seconds = remaining_percent / speed_percent_per_sec if speed_percent_per_sec > 0 else 0
                        result["speed"] = speed_percent_per_sec * 100  # convert to %/s
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 6 matched: {percent:.1%}, progress: {result['progress']:.3f}")

        # Padrão 7: "X articles sent" or similar
        match = re.search(r"(\d+)\s+articles?\s+sent", line, re.IGNORECASE)
        if match and self.total_articles:
            sent = int(match.group(1))
            if sent > self.uploaded_articles:  # Only update if it's new info
                self.uploaded_articles = sent
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        speed_articles_per_sec = sent / elapsed
                        remaining = self.total_articles - sent
                        eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                        result["progress"] = float(sent / self.total_articles)
                        result["speed"] = float(speed_articles_per_sec)
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 7 matched: {sent} articles sent, progress: {result['progress']:.3f}")

        # Padrão 8: "sending X/Y" or "transfer X/Y"
        match = re.search(r"(?:sending|transfer)\s+(\d+)\s*/\s*(\d+)", line, re.IGNORECASE)
        if match and not result["progress"]:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                self.uploaded_articles = current
                self.total_articles = total
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        speed_articles_per_sec = current / elapsed
                        remaining = total - current
                        eta_seconds = remaining / speed_articles_per_sec if speed_articles_per_sec > 0 else 0
                        result["progress"] = float(current / total)
                        result["speed"] = float(speed_articles_per_sec)
                        result["eta"] = int(eta_seconds)
                        if self.debug:
                            print(f"[DEBUG] Pattern 8 matched: sending {current}/{total}, progress: {result['progress']:.3f}")

        # Padrão 9: Finished uploading X MiB in YY:MM:SS.ZZZ (AA MiB/s)
        match = re.search(r"Finished uploading ([\d.]+) MiB.*?\(([\d.]+) MiB/s\)", line)
        if match:
            self.uploaded_size = float(match.group(1))
            speed = float(match.group(2))
            result["info"] = f"Concluído: {self.uploaded_size:.2f} MiB ({speed:.2f} MiB/s)"
            result["progress"] = 1.0  # 100% when finished
            if self.debug:
                print("[DEBUG] Pattern 9 matched: finished, progress: 1.0")

        self.lines_processed += 1
        return result

    def format_time(self, seconds: int) -> str:
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
        debug: bool = False,
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
        self.debug = debug
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

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                self.rar_file = str(self.folder_path.parent / f"{self.folder_path.name}.rar")
                if os.path.exists(self.rar_file):
                    size_mb = os.path.getsize(self.rar_file) / (1024 * 1024)
                    print(f"✅ RAR criado com sucesso: {size_mb:.2f} MB")
                    return True
                else:
                    print("❌ Erro: RAR não foi criado.")
                    return False
            else:
                print("❌ Erro ao criar RAR:")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            print(f"❌ Erro ao executar makerar.py: {e}")
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

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                self.par_file = os.path.splitext(self.rar_file)[0] + ".par2"
                if os.path.exists(self.par_file):
                    size_mb = os.path.getsize(self.par_file) / (1024 * 1024)
                    print(f"✅ Paridade criada com sucesso: {size_mb:.2f} MB")
                    return True
                else:
                    print("❌ Erro: paridade não foi criada.")
                    return False
            else:
                print("❌ Erro ao gerar paridade:")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            print(f"❌ Erro ao executar makepar.py: {e}")
            return False

    def run_upload(self) -> bool:
        """Executa upfolder.py com visualização de progresso melhorada."""
        if not self.rar_file:
            print("Erro: arquivo RAR não definido.")
            return False

        if not self.par_file:
            print("Erro: arquivo PAR2 não definido.")
            return False

        print("\n" + "=" * 60)
        print("ETAPA 3: Upload para Usenet")
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
            print(f"[DRY-RUN] Upload será feito com subject: {self.subject}")
            return True

        print("\n📤 Iniciando upload para Usenet...")
        print(f"   Subject: {self.subject}")
        if self.group:
            print(f"   Grupo:   {self.group}")
        print()

        try:
            parser = UploadProgressParser(debug=self.debug)
            
            print("📤 Iniciando upload... Aguarde o progresso aparecer.")
            
            # Inicializar barra de progresso com tqdm
            progress_bar = tqdm(
                total=100,
                desc="📤 Upload",
                unit="%",
                bar_format="{desc}: {percentage:3.1f}%|{bar}| {n:.1f}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                colour="green",
                ncols=100,
                initial=0,  # Começar em 0%
            )
            
            # Forçar exibição inicial da barra
            progress_bar.refresh()
            
            # Executar upfolder em modo real-time para capturar output
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            last_progress = 0.0
            progress_started = False
            estimated_progress = 0.0
            upload_start_time = None

            if proc.stdout:
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue

                    # Debug: mostrar todas as linhas se --debug estiver ativado
                    if self.debug:
                        print(f"[DEBUG] {line}")

                    parsed = parser.parse_line(line)
                    
                    # Mostrar informações importantes
                    if "INFO" in line or "Uploading" in line or "Finished" in line:
                        if parsed["info"]:
                            print(f"ℹ️  {parsed['info']}")
                        elif "Reading file" in line:
                            print(f"📖 {line.split('] ')[-1] if '] ' in line else line}")
                        elif "All file" in line:
                            print(f"✓  {line.split('] ')[-1] if '] ' in line else line}")
                    
                    # Detectar início do upload real
                    if "Uploading" in line and "article(s)" in line and not progress_started:
                        progress_started = True
                        upload_start_time = time.time()
                        print("📊 Barra de progresso ativada!")
                    
                    # Atualizar barra de progresso quando disponível
                    if parsed["progress"] is not None:
                        progress = parsed["progress"] * 100  # converter para porcentagem
                        
                        # Atualizar sempre que houver progresso
                        if progress != last_progress:
                            progress_bar.n = progress
                            progress_bar.refresh()
                            last_progress = progress
                            
                            # Debug: mostrar progresso detalhado
                            if self.debug:
                                debug_info = f"[DEBUG] Progress: {progress:.1f}%"
                                if parsed["speed"]:
                                    debug_info += f", Speed: {parsed['speed']:.2f} art/s"
                                if parsed["eta"]:
                                    eta_str = parser.format_time(parsed["eta"])
                                    debug_info += f", ETA: {eta_str}"
                                print(debug_info)
                    
                    # Estimativa de progresso baseada em tempo (fallback quando nyuu não dá feedback)
                    elif progress_started and upload_start_time and parser.total_articles:
                        elapsed = time.time() - upload_start_time
                        # Estimativa conservadora: assumir ~2-3 segundos por artigo em média
                        estimated_time_per_article = 3.0  # segundos (aumentado para teste)
                        estimated_total_time = parser.total_articles * estimated_time_per_article
                        
                        if estimated_total_time > 0:
                            estimated_progress = min(95, (elapsed / estimated_total_time) * 100)  # Máximo 95% até confirmação
                            
                            # Atualizar barra de estimativa a cada 0.5 segundos
                            if abs(estimated_progress - last_progress) >= 1.0:  # Mínimo 1% de mudança
                                progress_bar.n = estimated_progress
                                progress_bar.refresh()
                                last_progress = estimated_progress
                                
                                if self.debug:
                                    print(f"[DEBUG] Estimated progress: {estimated_progress:.1f}% ({elapsed:.1f}s elapsed)")

            # Finalizar barra de progresso
            progress_bar.n = 100
            progress_bar.close()
            print()

            rc = proc.wait()
            if rc == 0:
                print("✅ Upload concluído com sucesso!")
                return True
            else:
                print(f"❌ Erro: upfolder.py retornou código {rc}.")
                return False
        except Exception as e:
            print(f"❌ Erro ao executar upfolder.py: {e}")
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
            if not self.run_makerar():
                return 1
        else:
            if not self.run_makerar():  # tenta pular, mas valida existência
                return 1

        # Etapa 2: Gerar paridade
        if not self.skip_par:
            if not self.run_makepar():
                return 2
        else:
            if not self.run_makepar():  # tenta pular, mas valida existência
                return 2

        # Etapa 3: Upload
        if not self.skip_upload:
            if not self.run_upload():
                return 3
            # Limpar arquivos após upload bem-sucedido
            self.cleanup()
        else:
            print("\n⏭️  [--skip-upload] Upload foi pulado.")

        # Sucesso
        print("\n" + "=" * 60)
        print("✅ Workflow concluído com sucesso!")
        print("=" * 60)
        print("\nArquivos gerados:")
        print(f"  📦 RAR:  {self.rar_file}")
        print(f"  🛡️  PAR2: {self.par_file}")
        if not self.skip_upload:
            print(f"\n✉️  Upload concluído para: {self.subject}")
        print()
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
    p.add_argument(
        "--debug",
        action="store_true",
        help="Mostra output detalhado do nyuu para debug",
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
        debug=args.debug,
    )

    rc = orchestrator.run()
    sys.exit(rc)


if __name__ == "__main__":
    main()
