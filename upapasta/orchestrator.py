"""Orquestrador central do workflow do UpaPasta."""

from __future__ import annotations

import logging
import os
import re
import secrets
import shlex
import string
import time
from pathlib import Path
from typing import Optional

from ._pipeline import (
    DependencyChecker,
    PathResolver,
    PipelineReporter,
    do_cleanup_files,
    normalize_extensionless,
    print_rar_hints,
    print_skip_rar_hints,
    recalculate_resources,
    revert_extensionless,
    revert_obfuscation,
)
from .config import check_or_prompt_credentials
from .makepar import handle_par_failure, make_parity, obfuscate_and_par
from .makerar import make_rar
from .resources import get_total_size
from .ui import PhaseBar, format_time
from .upfolder import upload_to_usenet

logger = logging.getLogger("upapasta")


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
        return False


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
        skip_rar: bool = True,
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
        strong_obfuscate: bool = False,
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
        nzb_subject_prefix: Optional[str] = None,
        resume: bool = False,
    ):
        self.input_path = Path(input_path).absolute()
        self.dry_run = dry_run
        self.redundancy = redundancy
        self.post_size = post_size
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
        _cpu = os.cpu_count() or 4
        self.rar_threads = rar_threads if rar_threads is not None else _cpu
        self.par_threads = par_threads if par_threads is not None else _cpu
        self.par_memory_mb: int | None = None
        self.par_profile = par_profile
        self.nzb_conflict = nzb_conflict
        self.obfuscate = obfuscate
        self.strong_obfuscate = strong_obfuscate
        self.obfuscated_map: dict[str, str] = {}
        self.obfuscate_was_linked = False
        self.rar_password = rar_password
        self.par_slice_size = par_slice_size
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.verbose = verbose
        self.filepath_format = filepath_format
        self.parpar_extra_args = parpar_extra_args
        self.nyuu_extra_args = nyuu_extra_args
        self.rename_extensionless = rename_extensionless
        self.nzb_subject_prefix = nzb_subject_prefix
        self.resume = resume
        self._extensionless_map: dict[str, str] = {}
        self.each = False
        self.rar_file: Optional[str] = None
        self.par_file: Optional[str] = None
        self.nfo_file: Optional[str] = None
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
            skip_rar=not args.rar,
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
            strong_obfuscate=getattr(args, "strong_obfuscate", False),
            rar_password=args.password,
            par_slice_size=args.par_slice_size,
            upload_timeout=args.upload_timeout,
            upload_retries=args.upload_retries,
            verbose=args.verbose,
            max_memory_mb=args.max_memory,
            filepath_format=getattr(args, "filepath_format", "common"),
            parpar_extra_args=(
                shlex.split(args.parpar_args)
                if getattr(args, "parpar_args", None) else None
            ),
            nyuu_extra_args=(
                shlex.split(args.nyuu_args)
                if getattr(args, "nyuu_args", None) else None
            ),
            rename_extensionless=getattr(args, "rename_extensionless", False),
            resume=getattr(args, "resume", False),
        )

    @staticmethod
    def _generate_password(length: int = 16) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    def _path_resolver(self) -> PathResolver:
        return PathResolver(
            env_vars=self.env_vars,
            input_path=self.input_path,
            skip_rar=self.skip_rar,
            nzb_conflict=self.nzb_conflict,
            subject=self.subject,
        )

    def validate(self) -> bool:
        return DependencyChecker.validate(self.input_path, self.dry_run)

    def _resolve_nfo_path(self) -> tuple[str, str]:
        return self._path_resolver().nfo_path()

    def run_generate_nfo(self) -> bool:
        from .nfo import generate_nfo_folder, generate_nfo_single_file
        nfo_path, nzb_dir = self._resolve_nfo_path()
        nfo_filename = os.path.basename(nfo_path)
        try:
            os.makedirs(nzb_dir, exist_ok=True)
        except OSError:
            pass
        banner = self.env_vars.get("NFO_BANNER") or os.environ.get("NFO_BANNER")
        if not self.input_path.is_dir():
            ok = generate_nfo_single_file(str(self.input_path), nfo_path)
            if ok:
                self.nfo_file = nfo_path
                print(f"  ✔️ Arquivo NFO gerado: {nfo_filename} (salvo em: {nzb_dir})")
            return ok
        ok = generate_nfo_folder(str(self.input_path), nfo_path, banner=banner)
        if ok:
            self.nfo_file = nfo_path
            print(f"  ✔️ Arquivo NFO (descrição de pasta) gerado: {nfo_filename} (salvo em: {nzb_dir})")
        return ok

    def run_makerar(self) -> bool:
        if self.input_path.is_file():
            if self.rar_password:
                print("📦 Arquivo único com senha: criando RAR automaticamente.")
            elif self.obfuscate and not self.skip_rar:
                print("📦 Arquivo único com ofuscação e --rar: criando RAR.")
            elif self.skip_rar:
                # sem --rar explícito → upload direto (MKV/arquivo original)
                if self.obfuscate:
                    print(f"✅ Arquivo único com ofuscação: {self.input_path.name} (upload direto ofuscado + PAR2)")
                else:
                    print(f"✅ Arquivo único: {self.input_path.name} (upload direto, sem RAR)")
            # else: --rar explícito sem --obfuscate/--password → cria RAR normalmente

        if self.skip_rar:
            print_skip_rar_hints(self.input_path, self.filepath_format, self.backend)
            self.rar_file = None
            self.input_target = str(self.input_path)
            label = "pasta" if self.input_path.is_dir() else "arquivo"
            print(f"✅ Modo upload de {label}: {self.input_path.name}")
            return True

        print("\n" + "=" * 60)
        print("📦 ETAPA 1: Criar arquivo RAR")
        print("=" * 60)
        print_rar_hints(self.input_path, self.backend, self.rar_password, self.obfuscate)

        if self.dry_run:
            self.rar_file = str(self.input_path.parent / f"{self.input_path.stem}.rar")
            self.input_target = self.rar_file
            print("[DRY-RUN] pularia a criação do RAR.")
            print(f"[DRY-RUN] RAR seria criado em: {self.rar_file}")
            return True

        print(f"📥 Compactando {self.input_path.name}...")
        print("-" * 60)
        try:
            rc, generated_rar = make_rar(str(self.input_path), self.force, threads=self.rar_threads, password=self.rar_password)
            print("-" * 60)
            if rc == 0 and generated_rar:
                self.rar_file = generated_rar
                self.input_target = self.rar_file
                return True
            print(f"\n❌ Erro ao criar RAR. Veja o output acima para detalhes. (rc={rc})")
            return False
        except (FileNotFoundError, PermissionError, OSError) as e:
            label = "binário 'rar' não encontrado no PATH" if isinstance(e, FileNotFoundError) else str(e)
            print(f"❌ Erro ao criar RAR: {label}")
            return False

    def run_makepar(self) -> bool:
        if not self.input_target:
            print("Erro: caminho de entrada não definido.")
            return False

        resolver = self._path_resolver()

        if self.skip_par:
            par_path = (
                os.path.join(os.path.dirname(self.input_target), os.path.basename(self.input_target) + ".par2")
                if os.path.isdir(self.input_target)
                else resolver.par_file_path(self.input_target)
            )
            if os.path.exists(par_path):
                self.par_file = par_path
                size_mb = os.path.getsize(self.par_file) / (1024 * 1024)
                print(f"✅ Usando paridade existente: {size_mb:.2f} MB")
                return True
            print(f"❌ Erro: --skip-par mas arquivo {par_path} não existe.")
            return False

        print("\n" + "=" * 60)
        print("🛡️  ETAPA 2: Gerar arquivo de paridade PAR2")
        print("=" * 60)

        if self.obfuscate and not self.dry_run:
            return self._run_makepar_obfuscated(resolver)
        return self._run_makepar_plain(resolver)

    def _run_makepar_obfuscated(self, resolver: PathResolver) -> bool:
        print("🔐 Ofuscando arquivos e gerando paridade...")
        print("-" * 60)
        assert self.input_target is not None, "input_target não foi configurado"
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
        except (FileNotFoundError, PermissionError, OSError) as e:
            label = "binário de paridade não encontrado" if isinstance(e, FileNotFoundError) else str(e)
            print(f"❌ Erro ao ofuscar/gerar paridade: {label}")
            return False

        print("-" * 60)
        if rc != 0:
            print(f"\n❌ Erro ao ofuscar/gerar paridade (código {rc}).")
            return False

        assert obfuscated_path is not None, "obfuscated_path não definido"
        self.obfuscated_map = obf_map
        self.obfuscate_was_linked = was_linked
        self.input_target = obfuscated_path
        if self.rar_file:
            self.rar_file = obfuscated_path

        obf_basename = os.path.basename(obfuscated_path)
        obf_base_no_ext = re.sub(r'\.part\d+\.rar$', '', obf_basename)
        obf_base_no_ext = re.sub(r'\.rar$', '', obf_base_no_ext)
        self.subject = obf_base_no_ext
        print(f"✨ Subject ofuscado: {self.subject}")

        assert self.input_target is not None, "input_target não foi configurado após ofuscação"
        self.par_file = resolver.par_file_path(self.input_target)
        if os.path.exists(self.par_file):
            return True
        print("❌ Erro: Arquivo de paridade não encontrado após ofuscação.")
        return False

    def _run_makepar_plain(self, resolver: PathResolver) -> bool:
        print(f"🔐 Gerando paridade (perfil: {self.par_profile})...")
        print("-" * 60)
        assert self.input_target is not None, "input_target não foi configurado"
        self.par_file = (
            os.path.join(os.path.dirname(self.input_target), os.path.basename(self.input_target) + ".par2")
            if os.path.isdir(self.input_target)
            else resolver.par_file_path(self.input_target)
        )
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
                dry_run=self.dry_run,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            label = "binário de paridade não encontrado" if isinstance(e, FileNotFoundError) else str(e)
            print(f"❌ Erro ao gerar paridade: {label}")
            return False

        if rc != 0:
            print("-" * 60)
            print(f"\n❌ Erro ao gerar paridade (código {rc}).")
            assert self.input_target is not None, "input_target não foi configurado"
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
        return True

    def run_upload(self) -> bool:
        if not self.input_target:
            print("Erro: caminho de entrada não definido.")
            return False
        print("\n" + "=" * 60)
        print("📤 ETAPA 3: Upload para Usenet")
        print("=" * 60)

        try:
            assert self.input_target is not None, "input_target não foi configurado"
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
                folder_name=self.nzb_subject_prefix,
                strong_obfuscate=self.strong_obfuscate,
                resume=self.resume,
            )
            return rc == 0
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"\n❌ Erro durante upload: {e}")
            return False

    def _do_cleanup(self, on_error: bool = False, preserve_rar: bool = False) -> None:
        do_cleanup_files(self.rar_file, self.par_file, self.keep_files, on_error, preserve_rar)

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
        self.input_target = revert_obfuscation(
            self.obfuscate, self.input_target, self.input_path,
            self.obfuscate_was_linked, self.obfuscated_map, self.keep_files)

    def check_nzb_conflict_early(self) -> bool:
        return self._path_resolver().check_nzb_conflict(
            self.input_target, self.skip_upload, self.dry_run)

    def _recalculate_resources(self) -> tuple[dict, str, str]:
        res, rar_src, par_src = recalculate_resources(
            self.input_path, self._user_rar_threads, self._user_par_threads, self._user_memory_mb
        )
        if self._user_rar_threads is None:
            self.rar_threads = res["threads"]
        if self._user_par_threads is None:
            self.par_threads = res["par_threads"]
        self.par_memory_mb = res["max_memory_mb"]
        return res, rar_src, par_src

    def run(self) -> int:
        total_start = time.time()
        bar = PhaseBar()

        single_file_no_rar = self.input_path.is_file() and self.skip_rar and not self.obfuscate and not self.rar_password
        if self.skip_rar or single_file_no_rar:
            bar.skip("RAR")
        if self.skip_par:
            bar.skip("PAR2")
        if self.skip_upload:
            bar.skip("UPLOAD")

        from .config import load_env_file
        self.env_vars = load_env_file(self.env_file)

        if not self.skip_upload:
            self.env_vars = check_or_prompt_credentials(self.env_file)
            if not self.env_vars:
                return 3

        if not self.validate():
            return 1

        res, rar_src, par_src = self._recalculate_resources()

        nntp_connections = int(self.env_vars.get("NNTP_CONNECTIONS") or os.environ.get("NNTP_CONNECTIONS", "10"))
        total_bytes = get_total_size(str(self.input_path))
        eta_s = int(total_bytes / (nntp_connections * 500 * 1024))
        eta_str = format_time(eta_s) if eta_s > 0 else "N/A"

        PipelineReporter.print_header(
            self.input_path, res, self.subject, self.par_profile, self.post_size,
            self.rar_threads, self.par_threads, rar_src, par_src,
            self.obfuscate, self.rar_password, self.dry_run, eta_str, nntp_connections,
        )
        bar._render()

        # ── NFO ──────────────────────────────────────────────────────────────
        if not self.dry_run:
            bar.start("NFO")
            if not self.run_generate_nfo():
                bar.skip("NFO")
                print("Atenção: falha ao gerar .nfo, mas continuando...")
            else:
                bar.done("NFO")
        else:
            bar.skip("NFO")

        if not self.check_nzb_conflict_early():
            return 3

        # ── RAR ──────────────────────────────────────────────────────────────
        will_create_rar = not self.skip_rar
        if will_create_rar:
            bar.start("RAR")
            if not self.run_makerar():
                bar.error("RAR")
                self._cleanup_on_error()
                return 1
            bar.done("RAR")
        else:
            if not self.run_makerar():
                self._cleanup_on_error()
                return 1

        # ── Normalização de extensões ────────────────────────────────────────
        if self.rename_extensionless and self.skip_rar and not self.dry_run:
            target = self.input_target or str(self.input_path)
            self._extensionless_map = normalize_extensionless(target)
            if self._extensionless_map:
                print(f"🔧 Normalizadas {len(self._extensionless_map)} extensões → .bin")

        # ── PAR2 ─────────────────────────────────────────────────────────────
        if not self.skip_par:
            bar.start("PAR2")
            if not self.run_makepar():
                bar.error("PAR2")
                self._cleanup_on_error(preserve_rar=True)
                return 2
            bar.done("PAR2")
        else:
            if not self.run_makepar():
                self._cleanup_on_error()
                return 2

        stats = PipelineReporter.collect_stats(self.input_target, self.rar_file, self.par_file)

        # ── Upload ───────────────────────────────────────────────────────────
        if not self.skip_upload:
            bar.start("UPLOAD")
            if not self.run_upload():
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

        PipelineReporter.print_summary(
            stats, self.input_path, self.subject, self.rar_password,
            self.obfuscate, self.skip_upload, self.env_vars, self.group,
            self.nfo_file, self.rar_file, total_elapsed,
        )

        PipelineReporter.record_catalog_and_hook(
            env_vars=self.env_vars,
            stats=stats,
            input_path=self.input_path,
            subject=self.subject,
            rar_password=self.rar_password,
            obfuscate=self.obfuscate,
            skip_upload=self.skip_upload,
            group=self.group,
            nfo_file=self.nfo_file,
            elapsed=total_elapsed,
            skip_rar=self.skip_rar,
            obfuscated_map=self.obfuscated_map,
            redundancy=self.redundancy,
            nzb_path=self.generated_nzb,
        )

        return 0
