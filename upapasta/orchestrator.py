"""
orchestrator.py

Orquestrador central do workflow do UpaPasta.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import secrets
import shutil
import string
import time
from pathlib import Path
from typing import Optional

from .catalog import record_upload, run_post_upload_hook
from .config import check_or_prompt_credentials, render_template
from .makerar import make_rar
from .makepar import make_parity, obfuscate_and_par, generate_random_name, handle_par_failure
from .nzb import resolve_nzb_out, handle_nzb_conflict, resolve_nzb_template
from .upfolder import upload_to_usenet
from .resources import calculate_optimal_resources, get_total_size
from .ui import PhaseBar, format_time

logger = logging.getLogger("upapasta")


def normalize_extensionless(root: str, suffix: str = ".bin") -> dict[str, str]:
    """Renomeia recursivamente arquivos sem extensão para `<nome>{suffix}`.

    Mitigação para SABnzbd com "Unwanted Extensions": arquivos sem extensão
    recebem .txt no destino, quebrando hashes e estrutura. Renomear no upload
    (com reversão posterior) preserva os arquivos do remetente intactos e
    garante que o downloader receba arquivos com extensão estável.

    Retorna dict {novo_caminho_absoluto: caminho_original_absoluto}.
    Arquivo único também é suportado (root pode ser arquivo).
    """
    mapping: dict[str, str] = {}

    def _rename_one(path: str) -> None:
        base = os.path.basename(path)
        if "." in base and not base.startswith(".") and os.path.splitext(base)[1]:
            return  # já tem extensão
        if base.startswith("."):
            return  # dotfile: deixar
        new = path + suffix
        if os.path.exists(new):
            return  # colisão: pular para não sobrescrever
        os.rename(path, new)
        mapping[os.path.abspath(new)] = os.path.abspath(path)

    if os.path.isfile(root):
        _rename_one(root)
        return mapping

    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            _rename_one(os.path.join(dirpath, f))
    return mapping


def revert_extensionless(mapping: dict[str, str]) -> None:
    """Desfaz normalize_extensionless. Tolerante a entradas já revertidas."""
    for new_path, original in mapping.items():
        if os.path.exists(new_path) and not os.path.exists(original):
            try:
                os.rename(new_path, original)
            except OSError:
                pass


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
        filepath_format: str = "common",
        parpar_extra_args: Optional[list] = None,
        nyuu_extra_args: Optional[list] = None,
        rename_extensionless: bool = False,
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
        self.obfuscate_was_linked = False
        # --obfuscate implica senha: ocultar o nome sem proteger o conteúdo é
        # proteção pela metade. Senha aleatória gerada via secrets se não fornecida.
        if obfuscate and rar_password is None:
            self.rar_password: str | None = self._generate_password()
        else:
            self.rar_password = rar_password
        self.par_slice_size = par_slice_size
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.verbose = verbose
        self.filepath_format = filepath_format
        self.parpar_extra_args = parpar_extra_args
        self.nyuu_extra_args = nyuu_extra_args
        self.rename_extensionless = rename_extensionless
        self._extensionless_map: dict[str, str] = {}
        self.each = False  # controlado externamente via main()
        self.rar_file: Optional[str] = None
        self.par_file: Optional[str] = None
        self.nfo_file: Optional[str] = None
        # input_target is the path used for subsequent steps (string): either
        # the original folder/file or the rar file created for upload.
        self.input_target: Optional[str] = None
        self.env_vars: dict = {}
        self.generated_nzb: Optional[str] = None

    @classmethod
    def from_args(cls, args, input_path: str) -> "UpaPastaOrchestrator":
        """Cria instância a partir do namespace retornado por parse_args()."""
        return cls(
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
            filepath_format=getattr(args, "filepath_format", "common"),
            parpar_extra_args=(
                __import__("shlex").split(args.parpar_args)
                if getattr(args, "parpar_args", None) else None
            ),
            nyuu_extra_args=(
                __import__("shlex").split(args.nyuu_args)
                if getattr(args, "nyuu_args", None) else None
            ),
            rename_extensionless=getattr(args, "rename_extensionless", False),
        )

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
        env_vars = self.env_vars.copy()
        if self.nzb_conflict:
            env_vars["NZB_CONFLICT"] = self.nzb_conflict

        nzb_out_template = resolve_nzb_template(env_vars, self.input_path.is_dir(), self.skip_rar)

        # Usa o subject definido (que pode ser o nome original ou personalizado)
        basename = self.subject
        # Remove extensão se o subject terminar com uma extensão comum de vídeo
        video_exts = (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm")
        if basename.lower().endswith(video_exts):
            basename = os.path.splitext(basename)[0]

        nzb_filename = render_template(nzb_out_template, basename)

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
                self.nfo_file = nfo_path
                print(f"  ✔️ Arquivo NFO gerado: {nfo_filename} (salvo em: {nzb_dir})")
            return ok
        else:
            banner = env_vars.get("NFO_BANNER") or os.environ.get("NFO_BANNER")
            ok = generate_nfo_folder(str(self.input_path), nfo_path, banner=banner)
            if ok:
                self.nfo_file = nfo_path
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
            # Pasta com subpastas + parpar é o fluxo recomendado: parpar grava
            # a estrutura nos .par2 (filepath-format=common por padrão) e
            # SABnzbd/NZBGet recentes reconstroem a árvore no download.
            if self.input_path.is_dir() and self.backend == "parpar":
                has_subdirs = any(e.is_dir() for e in self.input_path.iterdir())
                if has_subdirs:
                    print(
                        f"✅ Pasta com subpastas + parpar (filepath-format={self.filepath_format}): "
                        "estrutura será preservada via PAR2."
                    )
                    print(
                        "   Dica: no SABnzbd, desative 'Recursive Unpacking' para preservar .zip internos\n"
                        "   e revise 'Unwanted Extensions' (use --rename-extensionless se houver arquivos sem extensão)."
                    )
                    # Pastas vazias não são preservadas: NNTP só carrega arquivos.
                    # Se houver subdirs sem arquivos, avisa e sugere RAR.
                    empty_dirs = []
                    for dp, _, files in os.walk(self.input_path):
                        if not files and dp != str(self.input_path):
                            # Diretório intermediário sem arquivos diretos.
                            # Ignora se contém subdirs com arquivos (folha vazia é o que importa).
                            try:
                                if not any(os.scandir(dp)):
                                    empty_dirs.append(os.path.relpath(dp, self.input_path))
                            except OSError:
                                pass
                    if empty_dirs:
                        print(
                            f"⚠️  {len(empty_dirs)} diretório(s) vazio(s) detectado(s) — não serão preservados no upload.\n"
                            f"    Usenet posta artigos (arquivos), não diretórios; pastas vazias somem no destino.\n"
                            f"    Se a estrutura vazia for relevante, remova --skip-rar para empacotar em RAR."
                        )
            elif self.input_path.is_dir() and self.backend == "par2":
                # par2 clássico não grava paths — aí sim o flat acontece.
                print(
                    "⚠️  Backend par2 + --skip-rar com pasta: par2 clássico não preserva hierarquia.\n"
                    "    Considere --backend parpar (recomendado) ou remova --skip-rar."
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

        # Dica: em 2026 o RAR não é mais necessário na maioria dos casos.
        if (
            self.input_path.is_dir()
            and self.backend == "parpar"
            and not self.rar_password
            and not self.obfuscate
        ):
            has_subdirs = any(e.is_dir() for e in self.input_path.iterdir())
            if has_subdirs:
                print(
                    "💡 Dica: para esta pasta com subpastas, considere --skip-rar.\n"
                    "   parpar preserva a hierarquia nos .par2 (filepath-format=common) e\n"
                    "   downloaders modernos reconstroem a árvore. Menos overhead, mesmo resultado."
                )

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
                rc, obfuscated_path, obf_map, was_linked = obfuscate_and_par(
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
                    filepath_format=self.filepath_format,
                    parpar_extra_args=self.parpar_extra_args,
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
            self.obfuscate_was_linked = was_linked
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
                    filepath_format=self.filepath_format,
                    parpar_extra_args=self.parpar_extra_args,
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
                nyuu_extra_args=self.nyuu_extra_args,
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
        if self._extensionless_map:
            revert_extensionless(self._extensionless_map)
            self._extensionless_map = {}
        self._do_cleanup(on_error=True, preserve_rar=preserve_rar)
        self._revert_obfuscation()

    def _revert_extension_normalization(self) -> None:
        if self._extensionless_map:
            revert_extensionless(self._extensionless_map)
            print(f"↩️  Restauradas {len(self._extensionless_map)} extensões originais")
            self._extensionless_map = {}

    def _revert_obfuscation(self) -> None:
        """Restaura o nome original da entrada ou remove links temporários.
        
        No fluxo --skip-rar com ofuscação:
        - Se foi usado hardlink: apenas remove o link (input_target).
        - Se foi usado rename (fallback): renomeia de volta para o original.
        """
        if not self.obfuscate or not self.input_target:
            return

        original = str(self.input_path)
        if self.input_target == original:
            return

        # Se foi hardlink, apenas deletamos a "visão" ofuscada (a menos que keep_files seja True)
        if self.obfuscate_was_linked:
            if self.keep_files:
                print(f"⚡ [--keep-files] Mantendo links de ofuscação: {os.path.basename(self.input_target)}")
                return
            if not os.path.exists(self.input_target):
                return
            print(f"🧹 Removendo links temporários de ofuscação: {os.path.basename(self.input_target)}")
            try:
                if os.path.isdir(self.input_target):
                    shutil.rmtree(self.input_target)
                else:
                    os.remove(self.input_target)
            except OSError as e:
                print(f"⚠️  Falha ao remover links de ofuscação: {e}")
            return

        # Fallback: se foi rename, reverte o rename
        if not os.path.exists(self.input_target):
            return
        if os.path.exists(original):
            return
        try:
            os.rename(self.input_target, original)
            print(f"↩️  Nome original restaurado: {self.input_path.name}")
            self.input_target = original
        except OSError as e:
            print(f"⚠️  Falha ao restaurar nome original ('{self.input_target}' → '{original}'): {e}")
            print(f"    AÇÃO MANUAL: renomeie '{os.path.basename(self.input_target)}' de volta para '{self.input_path.name}'")

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
        # Arquivo único com --obfuscate ou --password cria RAR automaticamente
        single_file_no_rar = self.input_path.is_file() and not self.obfuscate and not self.rar_password
        if self.skip_rar or single_file_no_rar:
            bar.skip("RAR")
        if self.skip_par:
            bar.skip("PAR2")
        if self.skip_upload:
            bar.skip("UPLOAD")

        # Carrega variáveis de ambiente (necessário para NFO e NZB paths mesmo sem upload)
        from .config import load_env_file
        self.env_vars = load_env_file(self.env_file)

        # Carrega credenciais e garante .env completo apenas se for fazer upload
        if not self.skip_upload:
            self.env_vars = check_or_prompt_credentials(self.env_file)
            if not self.env_vars:
                return 3

        if not self.validate():
            return 1

        # ... (recalculando recursos)
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
        if not self.dry_run:
            bar.start("NFO")
            if not self.run_generate_nfo():
                # bar.error("NFO")  # Omitido para não alarmar o usuário se for apenas mediainfo ausente
                bar.skip("NFO")
                print("Atenção: falha ao gerar .nfo, mas continuando...")
            else:
                bar.done("NFO")
        else:
            bar.skip("NFO")

        if not self.check_nzb_conflict_early():
            return 3

        # ── Etapa 1: RAR ────────────────────────────────────────────────────
        # RAR é criado quando: pasta sem --skip-rar, OU arquivo único com --obfuscate/--password
        will_create_rar = not self.skip_rar and (
            self.input_path.is_dir() or self.obfuscate or self.rar_password
        )
        if will_create_rar:
            bar.start("RAR")
            if not self.run_makerar():
                bar.error("RAR")
                self._cleanup_on_error()
                return 1
            bar.done("RAR")
        else:
            # skip ou arquivo único sem RAR: apenas valida e define input_target
            if not self.run_makerar():
                self._cleanup_on_error()
                return 1

        # ── Normalização de extensões (opt-in, antes do PAR2) ────────────────
        # Renomeia arquivos sem extensão para .bin para evitar que SABnzbd
        # adicione .txt e quebre hashes. Aplica-se quando o conteúdo vai como
        # está para o upload (skip-rar) e o usuário pediu explicitamente.
        if self.rename_extensionless and self.skip_rar and not self.dry_run:
            target = self.input_target or str(self.input_path)
            self._extensionless_map = normalize_extensionless(target)
            if self._extensionless_map:
                print(f"🔧 Normalizadas {len(self._extensionless_map)} extensões → .bin")

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

        # Guarda nome do RAR antes do cleanup (o arquivo será deletado)
        rar_display_name = os.path.basename(self.rar_file) if self.rar_file else None

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
            self._revert_extension_normalization()
            self._revert_obfuscation()
        else:
            print("\n⏭️  [--skip-upload] Upload foi pulado.")
            self._revert_extension_normalization()
            self._revert_obfuscation()

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
            raw_group = self.group or group_from_env or "(Não especificado)"
            if "," in raw_group:
                display_group = f"Pool ({len(raw_group.split(','))} grupos)"
            else:
                display_group = raw_group
            
            print(f"  » Subject da Postagem: {self.subject}")
            print(f"  » Grupo Usenet: {display_group}")

        print("\n📦 ARQUIVOS GERADOS:")
        print("-" * 25)
        if self.nfo_file and os.path.exists(self.nfo_file):
            print(f"  » NFO: {os.path.basename(self.nfo_file)}")
        if stats["rar_size_mb"] > 0:
            if rar_display_name:
                print(f"  » RAR: {rar_display_name} ({stats['rar_size_mb']:.2f} MB)")
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

        # ── Catálogo e hook pós-upload ────────────────────────────────────────
        # Resolve o caminho do NZB gerado (mesmo template usado pelo upfolder)
        working_dir = self.env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
        nzb_out, _nzb_abs_resolved = resolve_nzb_out(
            str(self.input_path), self.env_vars, self.input_path.is_dir(), self.skip_rar, working_dir, self.obfuscated_map
        )
        
        # Se houve conflito e renomeio, o arquivo real pode ter um sufixo.
        # Tentamos encontrar o arquivo real que foi gerado (até 10 tentativas de renomeio).
        _nzb_abs = _nzb_abs_resolved
        if not os.path.exists(_nzb_abs):
            base, ext = os.path.splitext(_nzb_abs)
            for i in range(1, 11):
                test_path = f"{base}_{i}{ext}"
                if os.path.exists(test_path):
                    _nzb_abs = test_path
                    break
            else:
                _nzb_abs = None

        self.generated_nzb = _nzb_abs

        # Grupo efetivo: pode ter sido selecionado do pool dentro do upfolder
        _raw_group = self.group or self.env_vars.get("USENET_GROUP") or ""
        _effective_group = _raw_group.split(",")[0].strip() if "," in _raw_group else _raw_group

        _tamanho = int(stats["rar_size_mb"] * 1024 * 1024) if stats["rar_size_mb"] else None
        _nome_ofuscado = self.subject if self.obfuscate else None

        try:
            record_upload(
                nome_original=self.input_path.name,
                nome_ofuscado=_nome_ofuscado,
                senha_rar=self.rar_password,
                tamanho_bytes=_tamanho,
                grupo_usenet=_effective_group or None,
                servidor_nntp=self.env_vars.get("NNTP_HOST") or os.environ.get("NNTP_HOST"),
                redundancia_par2=f"{self.redundancy}%" if self.redundancy else None,
                duracao_upload_s=round(total_elapsed, 1),
                num_arquivos_rar=stats.get("par2_file_count"),
                caminho_nzb=_nzb_abs,
                subject=self.subject,
            )
        except Exception as e:
            print(f"⚠️  Falha ao registrar no catálogo: {e}")

        if not self.skip_upload:
            run_post_upload_hook(
                self.env_vars,
                nzb_path=_nzb_abs,
                nfo_path=self.nfo_file,
                senha_rar=self.rar_password,
                nome_original=self.input_path.name,
                nome_ofuscado=_nome_ofuscado,
                tamanho_bytes=_tamanho,
                grupo_usenet=_effective_group or None,
            )

        return 0
