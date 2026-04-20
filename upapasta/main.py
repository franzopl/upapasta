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
import glob
import logging
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path

from .config import load_env_file, check_or_prompt_credentials, DEFAULT_ENV_FILE
from .makerar import make_rar
from .makepar import make_parity, obfuscate_and_par, generate_random_name
from .nzb import resolve_nzb_out, handle_nzb_conflict
from .upfolder import upload_to_usenet
from .resources import calculate_optimal_resources, get_total_size

logger = logging.getLogger("upapasta")


def setup_logging(verbose: bool = False, log_file: str | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    root = logging.getLogger("upapasta")
    root.setLevel(level)
    root.addHandler(handler)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(fh)


def format_time(seconds: int) -> str:
    """Formata segundos como HH:MM:SS."""
    if seconds < 0:
        return "00:00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PhaseBar:
    """Barra de progresso compacta com 4 fases: RAR → PAR2 → UPLOAD → DONE.

    Imprime uma linha de status sempre que uma fase muda de estado.
    Compatível com saída de subprocessos — não usa posicionamento de cursor.
    """

    PHASES = ("RAR", "PAR2", "UPLOAD", "DONE")
    _ICONS = {"pending": "⬜", "active": "▶ ", "done": "✅", "skipped": "⏭ ", "error": "❌"}

    def __init__(self) -> None:
        self._state: dict[str, str] = {p: "pending" for p in self.PHASES}
        self._elapsed: dict[str, float] = {}
        self._start: dict[str, float] = {}

    def start(self, phase: str) -> None:
        self._state[phase] = "active"
        self._start[phase] = time.time()
        self._render()

    def done(self, phase: str) -> None:
        if phase in self._start:
            self._elapsed[phase] = time.time() - self._start[phase]
        self._state[phase] = "done"
        self._render()

    def skip(self, phase: str) -> None:
        self._state[phase] = "skipped"

    def error(self, phase: str) -> None:
        if phase in self._start:
            self._elapsed[phase] = time.time() - self._start[phase]
        self._state[phase] = "error"
        self._render()

    def _fmt(self, phase: str) -> str:
        state = self._state[phase]
        icon = self._ICONS.get(state, "⬜")
        if state == "done":
            t = int(self._elapsed.get(phase, 0))
            return f"[{icon} {phase} {t // 60:02d}:{t % 60:02d}]"
        if state == "active":
            return f"[{icon} {phase}...]"
        if state in ("skipped", "error"):
            return f"[{icon} {phase}]"
        return f"[{icon} {phase}]"

    def _render(self) -> None:
        bar = "  ".join(self._fmt(p) for p in self.PHASES)
        print(f"\n{bar}")


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
        rar_password: str | None = None,
        par_slice_size: str | None = None,
        upload_timeout: int | None = None,
        upload_retries: int = 0,
        verbose: bool = False,
        max_memory_mb: int | None = None,
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
        self._user_rar_threads = rar_threads
        self._user_par_threads = par_threads
        self._user_memory_mb = max_memory_mb
        # Valores iniciais: serão recalculados em run() após medir tamanho da fonte
        self.rar_threads = rar_threads if rar_threads is not None else (os.cpu_count() or 4)
        self.par_threads = par_threads if par_threads is not None else (os.cpu_count() or 4)
        self.par_memory_mb: int | None = None
        self.par_profile = par_profile
        self.nzb_conflict = nzb_conflict
        self.obfuscate = obfuscate
        self.obfuscated_map: dict[str, str] = {}
        # Gera senha aleatória quando obfuscate=True e nenhuma senha foi fornecida
        if obfuscate and rar_password is None:
            self.rar_password: str | None = self._generate_password()
        else:
            self.rar_password = rar_password
        self.par_slice_size = par_slice_size
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.verbose = verbose
        self.rar_file: str | None = None
        self.par_file: str | None = None
        # input_target is the path used for subsequent steps (string): either
        # the original folder/file or the rar file created for upload.
        self.input_target: str | None = None
        self.env_vars: dict = {}

    @staticmethod
    def _generate_password(length: int = 16) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

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

    def _resolve_nfo_path(self) -> tuple[str, str]:
        """Retorna (nfo_path_absoluto, nfo_dir) onde o .nfo deve ser salvo."""
        is_folder = self.input_path.is_dir()

        env_vars = self.env_vars.copy()
        if self.nzb_conflict:
            env_vars["NZB_CONFLICT"] = self.nzb_conflict

        nzb_out_template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT") or "{filename}.nzb"

        basename = self.input_path.name
        if not is_folder:
            basename = self.input_path.stem
        nzb_filename = nzb_out_template.replace("{filename}", basename)

        if os.path.isabs(nzb_filename):
            nzb_dir = os.path.dirname(nzb_filename)
            nfo_filename = os.path.splitext(os.path.basename(nzb_filename))[0] + ".nfo"
        else:
            nzb_dir = env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
            nfo_filename = os.path.splitext(nzb_filename)[0] + ".nfo"

        return os.path.join(nzb_dir, nfo_filename), nzb_dir

    def run_generate_nfo(self) -> bool:
        """Gera arquivo .nfo baseado na entrada original."""
        from .nfo import generate_nfo_single_file, generate_nfo_folder

        is_folder = self.input_path.is_dir()

        env_vars = self.env_vars.copy()
        if self.nzb_conflict:
            env_vars["NZB_CONFLICT"] = self.nzb_conflict

        nfo_path, nzb_dir = self._resolve_nfo_path()
        nfo_filename = os.path.basename(nfo_path)

        try:
            os.makedirs(nzb_dir, exist_ok=True)
        except OSError:
            pass

        if not is_folder:
            ok = generate_nfo_single_file(str(self.input_path), nfo_path)
            if ok:
                print(f"  ✔️ Arquivo NFO gerado: {nfo_filename} (salvo em: {nzb_dir})")
            return ok
        else:
            banner = env_vars.get("NFO_BANNER") or os.environ.get("NFO_BANNER")
            ok = generate_nfo_folder(str(self.input_path), nfo_path, banner=banner)
            if ok:
                print(f"  ✔️ Arquivo NFO (descrição de pasta) gerado: {nfo_filename} (salvo em: {nzb_dir})")
            return ok

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
            rc, generated_rar = make_rar(str(self.input_path), self.force, threads=self.rar_threads, password=self.rar_password)
            if rc == 0 and generated_rar:
                print("-" * 60)
                self.rar_file = generated_rar
                self.input_target = self.rar_file
                return True
            else:
                print("-" * 60)
                print(f"\n❌ Erro ao criar RAR. Veja o output acima para detalhes. (rc={rc})")
                return False
        except FileNotFoundError:
            print("❌ Erro: binário 'rar' não encontrado no PATH.")
            return False
        except PermissionError as e:
            print(f"❌ Erro de permissão ao criar RAR: {e}")
            return False
        except OSError as e:
            print(f"❌ Erro de I/O ao criar RAR: {e}")
            return False

    def _par_file_path(self) -> str:
        """Retorna o caminho esperado do .par2 para self.input_target."""
        stem = os.path.splitext(self.input_target)[0]
        # Volumes RAR: "nome.part01" → "nome"
        if self.input_target.endswith(".rar") and ".part" in stem:
            stem = stem.rsplit(".part", 1)[0]
        return stem + ".par2"

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
                par_path = self._par_file_path()
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
                self.par_file = self._par_file_path()
            print(f"[DRY-RUN] PAR2 será criado em: {self.par_file}")
            return True

        if self.obfuscate:
            print("🔐 Ofuscando arquivos e gerando paridade...")
            print("-" * 60)

            if self.dry_run:
                obf_name = generate_random_name()
                print(f"[DRY-RUN] Renomearia para: {obf_name}")
                self.subject = obf_name
                self.par_file = self._par_file_path()
                return True

            try:
                rc, obfuscated_path, obf_map = obfuscate_and_par(
                    self.input_target,
                    redundancy=self.redundancy,
                    force=True,
                    backend=self.backend,
                    usenet=True,
                    post_size=self.post_size,
                    threads=self.par_threads,
                    profile=self.par_profile,
                    slice_size=self.par_slice_size,
                    memory_mb=self.par_memory_mb,
                )
            except FileNotFoundError:
                print("❌ Erro: binário de paridade não encontrado no PATH.")
                return False
            except PermissionError as e:
                print(f"❌ Erro de permissão ao gerar paridade: {e}")
                return False
            except OSError as e:
                print(f"❌ Erro de I/O ao gerar paridade: {e}")
                return False

            if rc != 0:
                print("-" * 60)
                print(f"\n❌ Erro ao ofuscar/gerar paridade (código {rc}).")
                return False

            print("-" * 60)

            # Atualiza caminhos para os nomes ofuscados
            self.obfuscated_map = obf_map
            self.input_target = obfuscated_path
            if self.rar_file:
                self.rar_file = obfuscated_path

            # Subject = base name ofuscado (sem extensão e sem .partNNN)
            obf_basename = os.path.basename(obfuscated_path)
            obf_base_no_ext = re.sub(r'\.part\d+\.rar$', '', obf_basename)
            obf_base_no_ext = re.sub(r'\.rar$', '', obf_base_no_ext)
            self.subject = obf_base_no_ext
            print(f"✨ Subject ofuscado: {self.subject}")

            self.par_file = self._par_file_path()
            if os.path.exists(self.par_file):
                return True
            else:
                print("❌ Erro: Arquivo de paridade não encontrado após ofuscação.")
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
                    slice_size=self.par_slice_size,
                    memory_mb=self.par_memory_mb,
                )
            except FileNotFoundError:
                print("❌ Erro: binário de paridade não encontrado no PATH.")
                return False
            except PermissionError as e:
                print(f"❌ Erro de permissão ao gerar paridade: {e}")
                return False
            except OSError as e:
                print(f"❌ Erro de I/O ao gerar paridade: {e}")
                return False

            if rc != 0:
                print("-" * 60)
                print(f"\n❌ Erro ao gerar paridade (código {rc}).")
                return self._handle_par_failure(rc)

            print("-" * 60)
            # O nome do arquivo par2 é baseado no nome original
            self.par_file = self._par_file_path()
            return True

    def _handle_par_failure(self, rc: int) -> bool:
        """
        Chamado quando o PAR2 falha. Tenta retry automático com perfil safe
        e threads reduzidas. Se o retry também falhar, preserva os RARs e
        orienta o usuário sobre como retomar.
        """
        # Limpa arquivos .par2 parciais (mas NÃO os RARs)
        if self.input_target:
            stem = os.path.splitext(self.input_target)[0]
            if self.input_target.endswith(".rar") and ".part" in stem:
                stem = stem.rsplit(".part", 1)[0]
            for f in glob.glob(glob.escape(stem) + "*.par2"):
                try:
                    os.remove(f)
                except OSError:
                    pass

        # Calcula configurações conservadoras para retry
        retry_threads = max(1, min(4, self.par_threads // 2))
        retry_profile = "safe"
        retry_memory_mb = max(512, (self.par_memory_mb or 2048) // 2)

        print(f"\n⚠️  Tentando novamente com configurações conservadoras...")
        print(f"   Perfil: {retry_profile} | Threads: {retry_threads} | Memória: {retry_memory_mb} MB")
        print("-" * 60)

        try:
            rc2 = make_parity(
                self.input_target,
                redundancy=self.redundancy,
                force=True,
                backend=self.backend,
                usenet=True,
                post_size=self.post_size,
                threads=retry_threads,
                profile=retry_profile,
                slice_size=self.par_slice_size,
                memory_mb=retry_memory_mb,
            )
        except Exception as e:
            print(f"❌ Erro no retry: {e}")
            rc2 = 5

        if rc2 == 0:
            print("-" * 60)
            self.par_file = self._par_file_path()
            print(f"✅ Paridade gerada com sucesso no retry (perfil {retry_profile}).")
            return True

        # Retry também falhou — preservar RARs e orientar o usuário
        print("-" * 60)
        print(f"\n❌ Falha persistente ao gerar paridade (código original {rc}, retry {rc2}).")

        if self.rar_file:
            rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(self.rar_file)[0])
            rar_volumes = glob.glob(glob.escape(rar_base) + ".part*.rar")
            count = len(rar_volumes)
            print(f"\n📦 Arquivos RAR preservados ({count} parte(s)) em:")
            print(f"   {os.path.dirname(self.rar_file)}")
            print(f"\n💡 Para retomar quando o problema for resolvido:")
            input_arg = str(self.input_path)
            extra = ""
            if self.par_profile != "safe":
                extra += " --par-profile safe"
            if self.par_threads != retry_threads:
                extra += f" --par-threads {retry_threads}"
            print(f"   upapasta {input_arg} --skip-rar --force{extra}")

        return False

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
                obfuscated_map=self.obfuscated_map or None,
                upload_timeout=self.upload_timeout,
                upload_retries=self.upload_retries,
                password=self.rar_password,
            )
            return rc == 0
        except FileNotFoundError as e:
            print(f"\n❌ Erro: arquivo não encontrado durante upload: {e}")
            return False
        except PermissionError as e:
            print(f"\n❌ Erro de permissão durante upload: {e}")
            return False
        except OSError as e:
            print(f"\n❌ Erro de I/O durante upload: {e}")
            return False

    def _do_cleanup(self, on_error: bool = False, preserve_rar: bool = False) -> None:
        """Remove arquivos RAR e PAR2 gerados."""
        if on_error:
            print("\n🧹 Limpando arquivos temporários devido a erro...")
        else:
            if self.keep_files:
                print("\n⚡ [--keep-files] Mantendo arquivos RAR e PAR2.")
                return
            print("\n🧹 Limpando arquivos temporários...")

        candidates: list[str] = []

        if self.rar_file and not preserve_rar:
            # Strip .partNNN suffix to get the base name for glob
            rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(self.rar_file)[0])
            rar_volumes = glob.glob(glob.escape(rar_base) + ".part*.rar")
            if rar_volumes:
                candidates.extend(rar_volumes)
            elif os.path.exists(self.rar_file):
                candidates.append(self.rar_file)
            base_name: str | None = rar_base
        elif self.rar_file and preserve_rar:
            rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(self.rar_file)[0])
            base_name = rar_base
        else:
            base_name = None

        if base_name is None and self.par_file:
            base_name = os.path.splitext(self.par_file)[0]

        if base_name:
            # Captura tanto o índice (.par2) quanto volumes (.vol*.par2) em uma passada
            candidates.extend(glob.glob(glob.escape(base_name) + "*.par2"))
        elif self.par_file and os.path.exists(self.par_file):
            candidates.append(self.par_file)

        # Deduplica preservando ordem
        files_to_delete = list(dict.fromkeys(candidates))

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

    def cleanup(self) -> None:
        self._do_cleanup(on_error=False)

    def _cleanup_on_error(self, preserve_rar: bool = False) -> None:
        self._do_cleanup(on_error=True, preserve_rar=preserve_rar)

    def check_nzb_conflict_early(self) -> bool:
        """Verifica conflito de NZB antecipadamente, antes de qualquer processamento."""
        if self.skip_upload or self.dry_run:
            return True

        input_path = str(self.input_target) if self.input_target else str(self.input_path)
        is_folder = os.path.isdir(input_path)

        env_vars = self.env_vars.copy()
        if self.nzb_conflict:
            env_vars['NZB_CONFLICT'] = self.nzb_conflict

        working_dir = env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
        nzb_out, nzb_out_abs = resolve_nzb_out(input_path, env_vars, is_folder, self.skip_rar, working_dir)
        _, _, _, ok = handle_nzb_conflict(nzb_out, nzb_out_abs, env_vars)
        return ok

    def run(self) -> int:
        """Executa o workflow completo."""

        stats = {"rar_size_mb": 0.0, "par2_size_mb": 0.0, "par2_file_count": 0}
        total_start = time.time()

        bar = PhaseBar()
        # Fases puladas não exibem temporizador — marca antes de renderizar
        if self.skip_rar or self.input_path.is_file():
            bar.skip("RAR")
        if self.skip_par:
            bar.skip("PAR2")
        if self.skip_upload:
            bar.skip("UPLOAD")

        # Carrega credenciais antes de exibir o cabeçalho
        if not self.skip_upload:
            self.env_vars = check_or_prompt_credentials(self.env_file)
            if not self.env_vars:
                return 3

        print("\n" + "=" * 60)
        print("🚀 UpaPasta — Workflow Completo de Upload para Usenet")
        print("=" * 60)
        print(f"📁 Entrada:      {self.input_path.name}")
        print(f"🎯 Perfil PAR2: {self.par_profile}")
        print(f"📊 Post-size:  {self.post_size or '(do perfil)'}")
        print(f"✉️  Subject:    {self.subject}")
        print(f"⚡ Threads RAR: {self.rar_threads}  PAR: {self.par_threads}")
        if self.obfuscate:
            print(f"🔒 Ofuscação: ativada")
            if self.rar_password:
                print(f"🔑 Senha RAR:  {self.rar_password}")
        if self.dry_run:
            print("⚠️  [DRY-RUN] Nenhum arquivo será criado ou enviado")

        # Estado inicial das fases
        bar._render()

        if not self.validate():
            return 1

        # Cálculo dinâmico de recursos (threads + memória) baseado no tamanho real da fonte
        total_bytes = get_total_size(str(self.input_path))
        res = calculate_optimal_resources(
            total_bytes,
            user_threads=self._user_rar_threads if self._user_rar_threads == self._user_par_threads else None,
            user_memory_mb=self._user_memory_mb,
        )
        # Aplicar apenas se o usuário não sobrescreveu manualmente cada um
        if self._user_rar_threads is None:
            self.rar_threads = res["threads"]
        if self._user_par_threads is None:
            self.par_threads = res["threads"]
        self.par_memory_mb = res["max_memory_mb"]

        conservative_tag = " [modo conservador]" if res["conservative_mode"] else ""
        logger.info(
            f"Recursos calculados: {res['threads']} threads, "
            f"{res['max_memory_mb']} MB RAM para PAR2"
            f"{conservative_tag} ({res['total_gb']} GB de entrada)"
        )

        # Etapa 0: NFO
        if not self.skip_upload and not self.dry_run:
            if not self.run_generate_nfo():
                print("Atenção: falha ao gerar .nfo, mas continuando...")

        if not self.check_nzb_conflict_early():
            return 3

        # ── Etapa 1: RAR ────────────────────────────────────────────────────
        if not self.skip_rar and not self.input_path.is_file():
            bar.start("RAR")
            if not self.run_makerar():
                bar.error("RAR")
                self._cleanup_on_error()
                return 1
            bar.done("RAR")
        else:
            # skip ou single-file: apenas valida
            if not self.run_makerar():
                self._cleanup_on_error()
                return 1

        # ── Etapa 2: PAR2 ───────────────────────────────────────────────────
        if not self.skip_par:
            bar.start("PAR2")
            if not self.run_makepar():
                bar.error("PAR2")
                # Preserva RARs: o _handle_par_failure já tentou retry e orientou o usuário
                self._cleanup_on_error(preserve_rar=True)
                return 2
            bar.done("PAR2")
        else:
            if not self.run_makepar():
                self._cleanup_on_error()
                return 2

        # Coletar tamanhos ANTES do upload/cleanup
        if self.input_target and os.path.exists(self.input_target):
            if os.path.isdir(self.input_target):
                total_size_bytes = 0
                for root, dirs, files in os.walk(self.input_target):
                    for file in files:
                        try:
                            total_size_bytes += os.path.getsize(os.path.join(root, file))
                        except OSError:
                            pass
                stats["rar_size_mb"] = total_size_bytes / (1024 * 1024)
                base_name = self.input_target
            else:
                try:
                    rar_stem = os.path.splitext(self.input_target)[0]
                    if rar_stem.endswith(tuple(f".part{n:02d}" for n in range(1, 100))):
                        rar_stem = rar_stem.rsplit(".", 1)[0]
                    rar_vols = glob.glob(glob.escape(rar_stem) + ".part*.rar")
                    if rar_vols:
                        stats["rar_size_mb"] = sum(os.path.getsize(f) for f in rar_vols) / (1024 * 1024)
                    else:
                        stats["rar_size_mb"] = os.path.getsize(self.input_target) / (1024 * 1024)
                    base_name = rar_stem
                except OSError:
                    stats["rar_size_mb"] = 0.0
                    base_name = os.path.splitext(self.input_target)[0]

            par_volumes = glob.glob(glob.escape(base_name) + "*.par2")
            stats["par2_file_count"] = len(par_volumes)
            stats["par2_size_mb"] = sum(
                os.path.getsize(f) for f in par_volumes if os.path.exists(f)
            ) / (1024 * 1024)

        # ── Etapa 3: Upload ──────────────────────────────────────────────────
        if not self.skip_upload:
            bar.start("UPLOAD")
            if not self.run_upload():
                bar.error("UPLOAD")
                self._cleanup_on_error()
                return 3
            bar.done("UPLOAD")
            self.cleanup()
        else:
            print("\n⏭️  [--skip-upload] Upload foi pulado.")

        total_elapsed = time.time() - total_start
        bar.done("DONE")

        # ── Sumário final ────────────────────────────────────────────────────
        print("=" * 60)
        print("🎉 WORKFLOW CONCLUÍDO COM SUCESSO 🎉")
        print("=" * 60)

        print("\n📊 RESUMO DA OPERAÇÃO:")
        print("-" * 25)
        print(f"  » Entrada de Origem: {self.input_path.name}")
        if self.obfuscate:
            print(f"  » Nome Ofuscado:    {self.subject}")
        if self.rar_password:
            print(f"  » Senha RAR:        {self.rar_password}")
        if not self.skip_upload:
            group_from_env = self.env_vars.get("USENET_GROUP")
            display_group = self.group or group_from_env or "(Não especificado)"
            print(f"  » Subject da Postagem: {self.subject}")
            print(f"  » Grupo Usenet: {display_group}")

        print("\n📦 ARQUIVOS GERADOS:")
        print("-" * 25)
        if stats["rar_size_mb"] > 0:
            if self.rar_file and os.path.exists(self.rar_file):
                print(f"  » RAR: {os.path.basename(self.rar_file)} ({stats['rar_size_mb']:.2f} MB)")
            elif os.path.isdir(self.input_path):
                print(f"  » Pasta: {self.input_path.name} ({stats['rar_size_mb']:.2f} MB)")
            else:
                print(f"  » Arquivo: {self.input_path.name} ({stats['rar_size_mb']:.2f} MB)")
        if stats["par2_file_count"] > 0:
            print(f"  » PAR2: {stats['par2_file_count']} arquivo(s) ({stats['par2_size_mb']:.2f} MB)")
        total_size = stats["rar_size_mb"] + stats["par2_size_mb"]
        print(f"  » Total: {total_size:.2f} MB")

        print(f"\n  » Tempo total: {format_time(int(total_elapsed))}")
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
        default=DEFAULT_ENV_FILE,
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
    p.add_argument(
        "--password",
        default=None,
        metavar="SENHA",
        help=(
            "Senha para o arquivo RAR. Com --obfuscate, uma senha aleatória é gerada "
            "automaticamente se esta opção for omitida. A senha é salva no NZB."
        ),
    )
    p.add_argument(
        "--par-slice-size",
        default=None,
        help="Tamanho de slice PAR2 manual (ex: 512K, 1M, 2M). Sobrescreve o cálculo automático.",
    )
    p.add_argument(
        "--upload-timeout",
        type=int,
        default=None,
        help="Timeout de conexão para nyuu em segundos (ex: 30).",
    )
    p.add_argument(
        "--upload-retries",
        type=int,
        default=0,
        help="Número de tentativas extras de upload em caso de falha transitória (padrão: 0).",
    )
    p.add_argument(
        "--max-memory",
        type=int,
        default=None,
        metavar="MB",
        help=(
            "Limite máximo de memória para PAR2 em MB (ex: 4096). "
            "Padrão: calculado automaticamente baseado na RAM disponível."
        ),
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Ativa saída de debug detalhada (logging nível DEBUG).",
    )
    p.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Grava log completo (nível DEBUG) em arquivo (ex: upapasta.log).",
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
    setup_logging(verbose=getattr(args, "verbose", False), log_file=getattr(args, "log_file", None))

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
        rar_password=args.password,
        par_slice_size=args.par_slice_size,
        upload_timeout=args.upload_timeout,
        upload_retries=args.upload_retries,
        verbose=args.verbose,
        max_memory_mb=args.max_memory,
    )

    rc = orchestrator.run()
    sys.exit(rc)


if __name__ == "__main__":
    main()
