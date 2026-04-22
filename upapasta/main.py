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

from __future__ import annotations

import argparse
import glob
import io
import logging
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import load_env_file, check_or_prompt_credentials, DEFAULT_ENV_FILE
from .makerar import make_rar
from .makepar import make_parity, obfuscate_and_par, generate_random_name, handle_par_failure
from .nzb import resolve_nzb_out, handle_nzb_conflict
from .upfolder import upload_to_usenet
from .resources import calculate_optimal_resources, get_total_size

logger = logging.getLogger("upapasta")


DEFAULT_LOG_DIR = os.path.join(os.path.dirname(os.path.expanduser("~/.config/upapasta/.env")), "logs")


class _TeeStream(io.TextIOBase):
    """Duplica escrita para stream original + arquivo de log."""

    def __init__(self, original: io.TextIOBase, log_fh: io.TextIOBase) -> None:
        self._original = original
        self._log = log_fh

    def write(self, s: str) -> int:
        self._original.write(s)
        self._original.flush()
        # Remove sequências ANSI antes de gravar no log
        clean = re.sub(r'\x1b\[[0-9;]*[mABCDEFGHJKSTfhilmns]', '', s)
        self._log.write(clean)
        self._log.flush()
        return len(s)

    def flush(self) -> None:
        self._original.flush()
        self._log.flush()

    @property
    def encoding(self):
        return getattr(self._original, 'encoding', 'utf-8')

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return self._original.isatty()


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
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


def setup_session_log(input_name: str, env_file: Optional[str] = None) -> tuple:
    """
    Cria arquivo de log da sessão em ~/.config/upapasta/logs/.
    Redireciona stdout para TeeStream que grava simultaneamente no terminal e no log.
    Retorna (caminho_do_log, file_handle) para fechar ao final.
    """
    log_dir = os.path.join(os.path.dirname(env_file or os.path.expanduser("~/.config/upapasta/.env")), "logs")
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Sanitiza nome para uso em arquivo
    safe_name = re.sub(r'[^\w.\-]', '_', input_name)[:80]
    log_path = os.path.join(log_dir, f"{ts}_{safe_name}.log")

    log_fh = open(log_path, "w", encoding="utf-8", buffering=1)
    log_fh.write(f"# UpaPasta — log de sessão\n# Início: {datetime.now().isoformat()}\n# Entrada: {input_name}\n\n")

    sys.stdout = _TeeStream(sys.__stdout__, log_fh)
    return log_path, log_fh


def teardown_session_log(log_fh: Optional[io.TextIOBase], log_path: str) -> None:
    """Restaura stdout e fecha o arquivo de log."""
    sys.stdout = sys.__stdout__
    if log_fh:
        log_fh.write(f"\n# Fim: {datetime.now().isoformat()}\n")
        log_fh.close()
    print(f"📄 Log salvo em: {log_path}")


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


class UpaPastaSession:
    """Context manager para garantir cleanup de recursos do UpaPastaOrchestrator."""
    
    def __init__(self, orchestrator: "UpaPastaOrchestrator"):
        self.orch = orchestrator

    def __enter__(self) -> "UpaPastaOrchestrator":
        return self.orch

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if exc_type is KeyboardInterrupt:
                print("\n⚠️  Interrompido pelo usuário (Ctrl+C).")
            try:
                self.orch._cleanup_on_error(preserve_rar=(exc_type is KeyboardInterrupt))
            except Exception:
                pass
        return False  # Propaga a exceção original


class UpaPastaOrchestrator:
    """Orquestra o workflow completo de upload para Usenet."""

    def __init__(
        self,
        input_path: str,
        dry_run: bool = False,
        redundancy: Optional[int] = None,
        post_size: Optional[str] = None,
        subject: Optional[str] = None,
        group: Optional[str] = None,
        skip_rar: bool = False,
        skip_par: bool = False,
        skip_upload: bool = False,
        force: bool = False,
        env_file: str = ".env",
        keep_files: bool = False,
        backend: str = "parpar",
        rar_threads: Optional[int] = None,
        par_threads: Optional[int] = None,
        par_profile: str = "balanced",
        nzb_conflict: Optional[str] = None,
        obfuscate: bool = False,
        rar_password: Optional[str] = None,
        par_slice_size: Optional[str] = None,
        upload_timeout: Optional[int] = None,
        upload_retries: int = 0,
        verbose: bool = False,
        max_memory_mb: Optional[int] = None,
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
        # --obfuscate e --password são independentes: obfuscate renomeia arquivos,
        # password protege o conteúdo RAR. Podem ser usados juntos ou separados.
        self.rar_password = rar_password
        self.par_slice_size = par_slice_size
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.verbose = verbose
        self.each = False  # controlado externamente via main()
        self.rar_file: Optional[str] = None
        self.par_file: Optional[str] = None
        # input_target is the path used for subsequent steps (string): either
        # the original folder/file or the rar file created for upload.
        self.input_target: Optional[str] = None
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
        if self.input_path.is_file():
            if self.obfuscate or self.rar_password:
                # Ofuscação real e senha exigem container RAR — cria automaticamente
                reason = "ofuscação" if self.obfuscate else "senha"
                print(f"📦 Arquivo único com {reason}: criando RAR automaticamente.")
                # Não define skip_rar — deixa cair no bloco de criação abaixo
            else:
                self.skip_rar = True
                print(f"✅ Arquivo único: {self.input_path.name} (upload direto, sem RAR)")

        if self.skip_rar:
            # Avisa quando a pasta tem subpastas (PAR2 de pastas com subpastas é problemático)
            if self.input_path.is_dir():
                has_subdirs = any(e.is_dir() for e in self.input_path.iterdir())
                if has_subdirs:
                    print(
                        "⚠️  A pasta contém subpastas. --skip-rar pode causar problemas de\n"
                        "    estrutura após o download (PAR2 não preserva hierarquia de diretórios).\n"
                        "    Recomendado: remova --skip-rar para usar RAR e preservar a estrutura."
                    )
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
                return handle_par_failure(
                    input_target=self.input_target,
                    original_rc=rc,
                    redundancy=self.redundancy,
                    backend=self.backend,
                    post_size=self.post_size,
                    threads=self.par_threads,
                    memory_mb=self.par_memory_mb,
                    slice_size=self.par_slice_size,
                    rar_file=self.rar_file,
                    par_profile=self.par_profile,
                )

            print("-" * 60)
            # O nome do arquivo par2 é baseado no nome original
            self.par_file = self._par_file_path()
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

        candidates: list = []
        base_name: Optional[str] = None

        if self.rar_file and not preserve_rar:
            # Strip .partNNN suffix to get the base name for glob
            rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(self.rar_file)[0])
            rar_volumes = glob.glob(glob.escape(rar_base) + ".part*.rar")
            if rar_volumes:
                candidates.extend(rar_volumes)
            elif os.path.exists(self.rar_file):
                candidates.append(self.rar_file)
            base_name = rar_base
        elif self.rar_file and preserve_rar:
            rar_base = re.sub(r'\.part\d+$', '', os.path.splitext(self.rar_file)[0])
            base_name = rar_base

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

        if not self.validate():
            return 1

        # Cálculo dinâmico de recursos ANTES do header para exibir valores reais
        total_bytes = get_total_size(str(self.input_path))
        res = calculate_optimal_resources(
            total_bytes,
            user_threads=self._user_rar_threads if self._user_rar_threads == self._user_par_threads else None,
            user_memory_mb=self._user_memory_mb,
        )
        if self._user_rar_threads is None:
            self.rar_threads = res["threads"]
        if self._user_par_threads is None:
            self.par_threads = res["par_threads"]
        self.par_memory_mb = res["max_memory_mb"]

        conservative_tag = " (conservador)" if res["conservative_mode"] else ""
        rar_src = f"manual" if self._user_rar_threads is not None else f"auto{conservative_tag}"
        par_src = f"manual" if self._user_par_threads is not None else f"auto{conservative_tag}"
        mem_gb = res["max_memory_mb"] / 1024

        print("\n" + "=" * 60)
        print("🚀 UpaPasta — Workflow Completo de Upload para Usenet")
        print("=" * 60)
        print(f"📁 Entrada:     {self.input_path.name}")
        print(f"📦 Tamanho:     {res['total_gb']} GB")
        print(f"🎯 Perfil PAR2: {self.par_profile}")
        print(f"📊 Post-size:   {self.post_size or '(do perfil)'}")
        print(f"✉️  Subject:     {self.subject}")
        print(f"⚡ Threads RAR: {self.rar_threads} ({rar_src})  PAR: {self.par_threads} ({par_src})")
        print(f"🧠 Memória PAR: {mem_gb:.1f} GB")
        if self.obfuscate:
            print(f"🔒 Ofuscação:   ativada")
            if self.rar_password:
                print(f"🔑 Senha RAR:   {self.rar_password}")
        if self.dry_run:
            print("⚠️  [DRY-RUN] Nenhum arquivo será criado ou enviado")

        # Estado inicial das fases
        bar._render()

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
                # Preserva RARs: o handle_par_failure já tentou retry e orientou o usuário
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

        # ── Etapa 3: Upload ──────────────────────────────────────────────────────
        if not self.skip_upload:
            bar.start("UPLOAD")
            upload_ok = self.run_upload()
            if not upload_ok:
                bar.error("UPLOAD")
                self._cleanup_on_error()
                return 3
            bar.done("UPLOAD")
            self.cleanup()
        else:
            print("\n⏭️  [--skip-upload] Upload foi pulado.")

        total_elapsed = time.time() - total_start
        bar.done("DONE")

        # ── Sumário final ──────────────────────────────────────────────────────
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


_USAGE_SHORT = """\
UpaPasta — uploader automatizado para Usenet

  Uso:  upapasta <caminho>  [opções]

  Exemplos rápidos:
    upapasta Filme.2024/              pasta inteira como um release (RAR + PAR2)
    upapasta Episodio.S01E01.mkv      arquivo único sem RAR
    upapasta Temporada.1/ --each      cada arquivo da pasta vira um release separado
    upapasta Pasta/ --obfuscate       release com nomes ofuscados
    upapasta Pasta/ --password abc    release com senha no RAR
    upapasta Pasta/ --dry-run         simula sem enviar nada

  Para ajuda completa:  upapasta --help
"""

_DESCRIPTION = "UpaPasta — uploader automatizado para Usenet"

_EPILOG = """\
COMPORTAMENTO PADRÃO
  Pasta   → RAR (store) + PAR2 (balanced) + upload → NZB + NFO
  Arquivo → PAR2 + upload direto (sem RAR) → NZB + NFO

  --obfuscate em arquivo único: cria RAR automaticamente (ofuscação real).
  --password  em arquivo único: cria RAR automaticamente (necessário para senha).
  --skip-rar  é incompatível com --password.

EXEMPLOS
  upapasta Filme.2024/                        pasta como release único
  upapasta Episodio.S01E01.mkv               arquivo único, sem RAR
  upapasta Temporada.1/ --each               cada arquivo da pasta separado
  upapasta Pasta/ --obfuscate                nomes aleatórios no NZB/upload
  upapasta Pasta/ --password "abc123"        RAR com senha injetada no NZB
  upapasta Pasta/ --obfuscate --password x   ofuscado + senha (independentes)
  upapasta Pasta/ --skip-rar --redundancy safe  sem RAR, mais paridade
  upapasta Pasta/ --dry-run                  simula sem enviar nada

CONFIGURAÇÃO
  Credenciais ficam em ~/.config/upapasta/.env
  Na primeira execução, um assistente interativo configura tudo automaticamente.
"""


def parse_args():
    p = argparse.ArgumentParser(
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Arquivo ou pasta a fazer upload",
    )

    # ── Opções essenciais ────────────────────────────────────────────────────
    essential = p.add_argument_group("opções essenciais")
    essential.add_argument(
        "--each",
        action="store_true",
        help=(
            "Processa cada arquivo da pasta individualmente. "
            "Ideal para temporadas: cada episódio vira um release separado com seu próprio NZB."
        ),
    )
    essential.add_argument(
        "--obfuscate",
        action="store_true",
        help=(
            "Renomeia RAR/PAR2 com nomes aleatórios antes do upload (privacidade). "
            "Em arquivo único, cria RAR automaticamente para ofuscação real."
        ),
    )
    essential.add_argument(
        "--password",
        default=None,
        metavar="SENHA",
        help=(
            "Protege o RAR com senha (injetada no NZB para extração automática). "
            "Em arquivo único, cria RAR automaticamente. Incompatível com --skip-rar."
        ),
    )
    essential.add_argument(
        "--skip-rar",
        action="store_true",
        help="Não cria RAR — envia os arquivos como estão. Incompatível com --password.",
    )
    essential.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula todo o processo sem criar ou enviar arquivos.",
    )

    # ── Opções de ajuste ─────────────────────────────────────────────────────
    tuning = p.add_argument_group("opções de ajuste")
    tuning.add_argument(
        "--par-profile",
        choices=("fast", "balanced", "safe"),
        default="balanced",
        help="Perfil PAR2: fast=5%%, balanced=10%% (padrão), safe=20%%",
    )
    tuning.add_argument(
        "-r", "--redundancy",
        type=int,
        default=None,
        metavar="PERCENT",
        help="Redundância PAR2 em %% (sobrescreve --par-profile)",
    )
    tuning.add_argument(
        "--keep-files",
        action="store_true",
        help="Mantém RAR e PAR2 após o upload",
    )
    tuning.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Grava log completo da sessão em arquivo",
    )
    tuning.add_argument(
        "--upload-retries",
        type=int,
        default=0,
        metavar="N",
        help="Tentativas extras de upload em caso de falha (padrão: 0)",
    )
    tuning.add_argument(
        "--verbose",
        action="store_true",
        help="Ativa log de debug detalhado",
    )

    # ── Opções avançadas ─────────────────────────────────────────────────────
    advanced = p.add_argument_group("opções avançadas")
    advanced.add_argument(
        "--backend",
        choices=("parpar", "par2"),
        default="parpar",
        help="Backend PAR2: parpar (padrão) ou par2",
    )
    advanced.add_argument(
        "--post-size",
        default=None,
        metavar="SIZE",
        help="Tamanho alvo de post (ex: 20M, 700K — sobrescreve perfil)",
    )
    advanced.add_argument(
        "--par-slice-size",
        default=None,
        metavar="SIZE",
        help="Override manual do slice PAR2 (ex: 512K, 1M, 2M)",
    )
    advanced.add_argument(
        "--rar-threads",
        type=int,
        default=None,
        metavar="N",
        help="Threads para RAR (padrão: CPUs disponíveis)",
    )
    advanced.add_argument(
        "--par-threads",
        type=int,
        default=None,
        metavar="N",
        help="Threads para PAR2 (padrão: CPUs disponíveis)",
    )
    advanced.add_argument(
        "--max-memory",
        type=int,
        default=None,
        metavar="MB",
        help="Limite de memória para PAR2 em MB (padrão: automático)",
    )
    advanced.add_argument(
        "-s", "--subject",
        default=None,
        help="Assunto da postagem (padrão: nome do arquivo/pasta)",
    )
    advanced.add_argument(
        "-g", "--group",
        default=None,
        help="Newsgroup (padrão: do .env)",
    )
    advanced.add_argument(
        "--nzb-conflict",
        choices=("rename", "overwrite", "fail"),
        default=None,
        help="Comportamento quando .nzb já existe: rename (padrão), overwrite, fail",
    )
    advanced.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        metavar="PATH",
        help="Caminho alternativo para o .env (padrão: ~/.config/upapasta/.env)",
    )
    advanced.add_argument(
        "--upload-timeout",
        type=int,
        default=None,
        metavar="N",
        help="Timeout de conexão para nyuu em segundos",
    )
    advanced.add_argument(
        "-f", "--force",
        action="store_true",
        help="Sobrescreve RAR/PAR2 existentes",
    )
    advanced.add_argument(
        "--skip-par",
        action="store_true",
        help="Pula geração de paridade",
    )
    advanced.add_argument(
        "--skip-upload",
        action="store_true",
        help="Pula o upload (útil para gerar apenas RAR/PAR2)",
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


def _validate_flags(args) -> bool:
    """Valida combinações de flags incompatíveis. Retorna False se há erro fatal."""
    if args.skip_rar and args.password:
        print(
            "❌  --skip-rar e --password são incompatíveis.\n"
            "    Sem RAR não é possível proteger o conteúdo com senha.\n"
            "    Remova --skip-rar ou remova --password."
        )
        return False

    if args.each:
        p = Path(args.input)
        if not p.is_dir():
            print("❌  --each requer uma pasta como entrada.")
            return False

    if args.skip_rar and args.obfuscate:
        print(
            "⚠️   Ofuscação parcial: sem RAR, o nome real dos arquivos fica exposto\n"
            "    nos headers NNTP mesmo com --obfuscate.\n"
            "    Para ofuscação completa, remova --skip-rar.\n"
            "    Continuando em 3s... (Ctrl+C para cancelar)"
        )
        import time as _time
        _time.sleep(3)

    return True


def _make_orchestrator(args, input_path: str) -> "UpaPastaOrchestrator":
    return UpaPastaOrchestrator(
        input_path=input_path,
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


def main():
    args = parse_args()

    # Sem argumentos: exibe uso amigável e sai
    if args.input is None:
        print(_USAGE_SHORT)
        sys.exit(0)

    setup_logging(verbose=getattr(args, "verbose", False), log_file=getattr(args, "log_file", None))

    if not _validate_flags(args):
        sys.exit(1)

    needs_rar = True
    try:
        p = Path(args.input)
        if p.exists() and p.is_file() and not args.obfuscate and not args.password:
            needs_rar = False
    except Exception:
        pass

    if not check_dependencies(needs_rar):
        sys.exit(1)

    # ── Modo --each: processa cada arquivo da pasta individualmente ──────────
    if args.each:
        folder = Path(args.input)
        files = sorted(f for f in folder.iterdir() if f.is_file())
        if not files:
            print(f"❌  Nenhum arquivo encontrado em: {folder}")
            sys.exit(1)

        print(f"📂 Modo --each: {len(files)} arquivo(s) em {folder.name}")
        failed: list[str] = []

        for i, file_path in enumerate(files, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(files)}] {file_path.name}")
            print("=" * 60)

            input_name = file_path.name
            log_path, log_fh = setup_session_log(input_name, env_file=args.env_file)
            rc = 1
            try:
                orchestrator = _make_orchestrator(args, str(file_path))
                with UpaPastaSession(orchestrator) as orch:
                    rc = orch.run()
            except KeyboardInterrupt:
                rc = 130
                teardown_session_log(log_fh, log_path)
                print("\n⚠️  Interrompido pelo usuário.")
                sys.exit(rc)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                teardown_session_log(log_fh, log_path)

            if rc != 0:
                failed.append(file_path.name)

        if failed:
            print(f"\n❌  {len(failed)} arquivo(s) com falha:")
            for name in failed:
                print(f"    • {name}")
            sys.exit(1)
        sys.exit(0)

    # ── Modo normal: um único input ──────────────────────────────────────────
    input_name = Path(args.input).name
    log_path, log_fh = setup_session_log(input_name, env_file=args.env_file)

    rc = 1
    try:
        orchestrator = _make_orchestrator(args, args.input)
        with UpaPastaSession(orchestrator) as orch:
            rc = orch.run()
    except KeyboardInterrupt:
        rc = 130
    except Exception:
        rc = 1
        import traceback
        traceback.print_exc()
    finally:
        teardown_session_log(log_fh, log_path)

    sys.exit(rc)


if __name__ == "__main__":
    main()
