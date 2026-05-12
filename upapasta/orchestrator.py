"""Orquestrador central do workflow do UpaPasta."""

from __future__ import annotations

import glob
import logging
import os
import re
import secrets
import shlex
import shutil
import string
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

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
from .i18n import _
from .make7z import make_7z
from .makepar import (
    deep_obfuscate_tree,
    generate_random_name,
    handle_par_failure,
    make_parity,
    perform_obfuscation,
    rename_par2_files,
)
from .makerar import make_rar
from .nzb import enrich_nzb_metadata, resolve_nzb_out
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

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        if exc_type is not None:
            if exc_type is KeyboardInterrupt:
                print(_("\n⚠️  Interrompido pelo usuário (Ctrl+C)."))
            try:
                self.orch._cleanup_on_error(preserve_rar=(exc_type is KeyboardInterrupt))
            except Exception:
                pass


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
        rar_password: Optional[str] = None,
        par_slice_size: Optional[str] = None,
        upload_timeout: Optional[int] = None,
        upload_retries: int = 0,
        verbose: bool = False,
        max_memory_mb: Optional[int] = None,
        filepath_format: str = "common",
        parpar_extra_args: Optional[list[str]] = None,
        nyuu_extra_args: Optional[list[str]] = None,
        rename_extensionless: bool = False,
        nzb_subject_prefix: Optional[str] = None,
        resume: bool = False,
        compressor: str = "rar",
        tmdb: bool = False,
        tmdb_id: Optional[int] = None,
        nfo_template: Optional[str] = None,
        verify_uploads: bool = False,
        check_delay: int = 5,
        check_retry_delay: int = 30,
        check_tries: int = 5,
        check_host: Optional[str] = None,
        check_port: Optional[int] = None,
        check_user: Optional[str] = None,
        check_password: Optional[str] = None,
        use_ramdisk: bool = False,
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
        self.compressor = compressor
        self.tmdb = tmdb
        self.tmdb_id = tmdb_id
        self.nfo_template = nfo_template

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
        self.env_vars: dict[str, str] = {}
        self.generated_nzb: Optional[str] = None
        self.tmdb_data: Optional[dict[str, Any]] = None
        self.verify_uploads = verify_uploads
        self.check_delay = check_delay
        self.check_retry_delay = check_retry_delay
        self.check_tries = check_tries
        self.check_host = check_host
        self.check_port = check_port
        self.check_user = check_user
        self.check_password = check_password
        self.use_ramdisk = use_ramdisk
        self.ramdisk_path: Optional[str] = None

    @classmethod
    def from_args(
        cls,
        args: Any,
        input_path: str,
        env_vars: Optional[dict[str, str]] = None,
    ) -> "UpaPastaOrchestrator":
        """Cria instância a partir do namespace retornado por parse_args()."""
        if env_vars is None:
            from .config import load_env_file, resolve_env_file

            env_file = getattr(args, "env", None)
            env_vars = load_env_file(resolve_env_file(env_file))

        # Decisão do compressor: apenas define se houver flag explícita de compressão
        if getattr(args, "rar", False):
            final_compressor = "rar"
        elif getattr(args, "sevenzip", False):
            final_compressor = "7z"
        elif getattr(args, "compress", False):
            final_compressor = env_vars.get("DEFAULT_COMPRESSOR", "rar")
        else:
            final_compressor = env_vars.get("DEFAULT_COMPRESSOR", "rar")

        # Comportamento padrão 2026: upload direto (sem compactação)
        # Compactar apenas se explicitamente solicitado via --rar, --7z, --compress, ou --password
        skip_pack = True

        # Sobrescritas que forçam compactação:
        if (
            getattr(args, "rar", False)
            or getattr(args, "sevenzip", False)
            or getattr(args, "compress", False)
            or args.password
        ):
            skip_pack = False

        # Sobrescrita que força pular (deprecated)
        if getattr(args, "skip_rar_deprecated", False):
            skip_pack = True

        orch = cls(
            input_path=input_path,
            dry_run=args.dry_run,
            redundancy=args.redundancy,
            backend=args.backend,
            post_size=args.post_size,
            subject=args.subject,
            group=args.group,
            skip_rar=skip_pack,
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
                shlex.split(args.parpar_args) if getattr(args, "parpar_args", None) else None
            ),
            nyuu_extra_args=(
                shlex.split(args.nyuu_args) if getattr(args, "nyuu_args", None) else None
            ),
            rename_extensionless=getattr(args, "rename_extensionless", False),
            resume=getattr(args, "resume", False),
            compressor=final_compressor,
            tmdb=getattr(args, "tmdb", False),
            tmdb_id=getattr(args, "tmdb_id", None),
            nfo_template=getattr(args, "nfo_template", None) or env_vars.get("NFO_TEMPLATE"),
            verify_uploads=getattr(args, "verify_uploads", False),
            check_delay=getattr(args, "check_delay", 5),
            check_retry_delay=getattr(args, "check_retry_delay", 30),
            check_tries=getattr(args, "check_tries", 5),
            check_host=getattr(args, "check_host", None),
            check_port=getattr(args, "check_port", None),
            check_user=getattr(args, "check_user", None),
            check_password=getattr(args, "check_password", None),
            use_ramdisk=getattr(args, "use_ramdisk", False),
        )

        # ── Validação e auto-ativação de ramdisk ──────────────────────────────
        import platform

        use_ramdisk_explicit = getattr(args, "use_ramdisk", False)
        no_ramdisk_explicit = getattr(args, "no_ramdisk", False)

        if platform.system() != "Linux":
            if use_ramdisk_explicit:
                logger.warning(
                    _(
                        "--use-ramdisk é suportado apenas em Linux. Flag será ignorado nesta plataforma."
                    )
                )
            orch.use_ramdisk = False
        elif no_ramdisk_explicit:
            logger.info(_("💾 Ramdisk desativado explicitamente (--no-ramdisk)"))
            orch.use_ramdisk = False
        elif use_ramdisk_explicit:
            orch.use_ramdisk = True
        else:
            orch.use_ramdisk, reason = cls._should_enable_ramdisk_auto(input_path)
            if not orch.use_ramdisk and reason:
                logger.info(reason)

        return orch

    @classmethod
    def _should_enable_ramdisk_auto(cls, input_path: str) -> tuple[bool, str | None]:
        """
        Decide se deve ativar ramdisk automaticamente.
        Valida: SO, filesystem suporte, RAM disponível.
        Retorna: (ativado: bool, motivo_se_desativado: str | None)
        """
        try:
            import platform

            if platform.system() != "Linux":
                return False, _("💾 Ramdisk disponível apenas em Linux")

            dev_shm = "/dev/shm"
            if not os.path.exists(dev_shm):
                return False, _("💾 Ramdisk não disponível: /dev/shm não encontrado")

            input_dir = os.path.dirname(os.path.abspath(input_path))

            if not cls._test_symlink_support(input_dir):
                return (
                    False,
                    _(
                        "💾 Ramdisk não disponível: filesystem não suporta symlinks "
                        "(tente em ext4, BTRFS, NFS ou WSL em NTFS)"
                    ),
                )

            stat_shm = os.statvfs(dev_shm)
            available_bytes = stat_shm.f_bavail * stat_shm.f_frsize
            available_gb = available_bytes / (1024**3)

            orch_temp = object.__new__(cls)
            orch_temp.input_target = input_path
            try:
                estimated_par2 = orch_temp._estimate_par2_size()
            except Exception:
                estimated_par2 = 0

            if estimated_par2 == 0:
                return False, _(
                    "💾 Ramdisk não disponível: não foi possível estimar tamanho do PAR2"
                )

            margin = 0.35
            required_bytes = int(estimated_par2 * (1 + margin))
            required_gb = required_bytes / (1024**3)

            if available_bytes >= required_bytes:
                logger.info(
                    _(
                        "💾 Ramdisk ativado automaticamente "
                        "({avail:.1f}GB > {req:.1f}GB com margem 35%)"
                    ).format(avail=available_gb, req=required_gb)
                )
                return True, None
            else:
                return (
                    False,
                    _(
                        "💾 Ramdisk não disponível: RAM insuficiente "
                        "({avail:.1f}GB < {req:.1f}GB necessário com margem 35%)"
                    ).format(avail=available_gb, req=required_gb),
                )

        except Exception as e:
            return False, _("💾 Ramdisk não disponível: erro ao validar ({e})").format(e=e)

    @staticmethod
    def _test_symlink_support(test_dir: str) -> bool:
        """
        Testa se o filesystem suporta symlinks.
        Cria symlink de teste e remove se bem-sucedido.
        """
        try:
            test_link = os.path.join(test_dir, ".upapasta_symlink_test")
            test_target = os.path.join(test_dir, ".upapasta_symlink_target")

            Path(test_target).touch()
            os.symlink(test_target, test_link)
            os.remove(test_link)
            os.remove(test_target)
            return True
        except (OSError, NotImplementedError):
            try:
                Path(test_target).unlink(missing_ok=True)
                Path(test_link).unlink(missing_ok=True)
            except Exception:
                pass
            return False

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

    def run_generate_nfo(self, bar: Optional[PhaseBar] = None) -> bool:
        from .nfo import (
            generate_nfo_folder,
            generate_nfo_from_template,
            generate_nfo_single_file,
        )

        nfo_path, nzb_dir = self._resolve_nfo_path()
        nfo_filename = os.path.basename(nfo_path)
        try:
            os.makedirs(nzb_dir, exist_ok=True)
        except OSError:
            pass

        self.tmdb_data = None
        # ... (TMDb lookup logic same as before, but saving to self.tmdb_data)

        # Tenta buscar metadados no TMDb se houver chave e flag --tmdb
        api_key = self.env_vars.get("TMDB_API_KEY")
        if api_key and self.tmdb and not self.dry_run:
            from .tmdb import parse_title_and_year, search_media

            if bar:
                bar.log(_("Buscando metadados no TMDb..."))

            # Determina tipo de mídia (movie/tv)
            from .catalog import detect_category

            cat = detect_category(self.input_path.name)
            media_type = "tv" if cat == "TV" else "movie"

            lookup_data: Optional[dict[str, Any]] = None

            if self.tmdb_id:
                # Busca direta por ID se fornecido
                from .tmdb import _get_details

                lookup_data = {"id": self.tmdb_id}
                details = _get_details(
                    api_key,
                    self.tmdb_id,
                    media_type,
                    self.env_vars.get("TMDB_LANGUAGE", "pt-BR"),
                )
                if details:
                    lookup_data.update(details)
            else:
                # Busca automática por nome
                clean_title, year = parse_title_and_year(self.input_path.name)
                strict_mode = self.env_vars.get("TMDB_STRICT", "true").lower() == "true"
                lookup_data, suggestions = search_media(
                    api_key,
                    clean_title,
                    year=year,
                    media_type=media_type,
                    language=self.env_vars.get("TMDB_LANGUAGE", "pt-BR"),
                    strict=strict_mode,
                )

                if lookup_data and bar:
                    title = lookup_data.get("title") or lookup_data.get("name")
                    bar.log(_("✅ TMDb: {title} encontrado.").format(title=title))
                elif not lookup_data and bar and not self.tmdb_id:
                    # Se tínhamos chave mas não veio nada, pode ser por conta do strict
                    bar.log(
                        _("⚠️ TMDb: nenhum resultado confiável para '{title}'.").format(
                            title=clean_title
                        )
                    )
                    if suggestions:
                        # Lista top 3 sugestões
                        bar.log(_("Sugestões encontradas (use --tmdb-id):"))
                        for s in suggestions[:3]:
                            s_title = s.get("title") or s.get("name")
                            s_date = s.get("release_date") or s.get("first_air_date") or ""
                            s_year = s_date[:4] if len(s_date) >= 4 else "N/A"
                            s_id = s.get("id")
                            bar.log(f"  • {s_title} ({s_year}) ID: {s_id}")

                self.tmdb_data = lookup_data

        if self.nfo_template and os.path.exists(self.nfo_template):
            ok = generate_nfo_from_template(
                self.nfo_template, str(self.input_path), nfo_path, tmdb_metadata=self.tmdb_data
            )
            if ok:
                self.nfo_file = nfo_path
                if not bar:
                    print(
                        _("  ✔️ NFO gerado a partir do template: {name}").format(
                            name=os.path.basename(self.nfo_template)
                        )
                    )
                return True
            else:
                if not bar:
                    print(_("⚠️ Falha ao usar template de NFO. Usando geração automática."))

        banner = self.env_vars.get("NFO_BANNER") or os.environ.get("NFO_BANNER")
        if not self.input_path.is_dir():
            ok = generate_nfo_single_file(
                str(self.input_path), nfo_path, tmdb_metadata=self.tmdb_data
            )
            if ok:
                self.nfo_file = nfo_path
                if not bar:
                    print(
                        _("  ✔️ Arquivo NFO gerado: {nfo_filename} (salvo em: {nzb_dir})").format(
                            nfo_filename=nfo_filename, nzb_dir=nzb_dir
                        )
                    )
            return ok
        ok = generate_nfo_folder(
            str(self.input_path), nfo_path, banner=banner, tmdb_metadata=self.tmdb_data
        )
        if ok:
            self.nfo_file = nfo_path
            if not bar:
                print(
                    _(
                        "  ✔️ Arquivo NFO (descrição de pasta) gerado: {nfo_filename} (salvo em: {nzb_dir})"
                    ).format(nfo_filename=nfo_filename, nzb_dir=nzb_dir)
                )
        return ok

    def run_makerar(self, bar: Optional[PhaseBar] = None) -> bool:
        """Alias para run_compression por compatibilidade com testes."""
        return self.run_compression(bar=bar)

    def run_compression(self, bar: Optional[PhaseBar] = None) -> bool:
        if self.input_path.is_file():
            if not bar:
                msg_pfx = "RAR" if self.compressor == "rar" else "7z"
                if self.rar_password:
                    print(
                        _("📦 Arquivo único com senha: criando {pfx} automaticamente.").format(
                            pfx=msg_pfx
                        )
                    )
                elif self.obfuscate and not self.skip_rar:
                    print(
                        _("📦 Arquivo único com ofuscação e --rar: criando {pfx}.").format(
                            pfx=msg_pfx
                        )
                    )

                elif self.skip_rar:
                    # sem --rar explícito → upload direto (MKV/arquivo original)
                    if self.obfuscate:
                        print(
                            _(
                                "✅ Arquivo único com ofuscação: {name} (upload direto ofuscado + PAR2)"
                            ).format(name=self.input_path.name)
                        )
                    else:
                        print(
                            _("✅ Arquivo único: {name} (upload direto, sem RAR)").format(
                                name=self.input_path.name
                            )
                        )

        if self.skip_rar:
            if not bar:
                print_skip_rar_hints(self.input_path, self.filepath_format, self.backend)
            self.rar_file = None
            self.input_target = str(self.input_path)
            if not bar:
                label = _("pasta") if self.input_path.is_dir() else _("arquivo")
                print(
                    _("✅ Modo upload de {label}: {name}").format(
                        label=label, name=self.input_path.name
                    )
                )
            return True

        if not bar:
            print("\n" + "=" * 60)
            msg_pfx = "RAR" if self.compressor == "rar" else "7z"
            print(_("📦 ETAPA 1: Criar arquivo {pfx}").format(pfx=msg_pfx))
            print("=" * 60)
            print_rar_hints(self.input_path, self.backend, self.rar_password, self.obfuscate)

        ext = ".7z" if self.compressor == "7z" else ".rar"
        if self.dry_run:
            self.rar_file = str(self.input_path.parent / f"{self.input_path.stem}{ext}")
            self.input_target = self.rar_file
            if not bar:
                print(_("[DRY-RUN] pularia a criação do arquivo compactado."))
                print(_("[DRY-RUN] Arquivo seria criado em: {path}").format(path=self.rar_file))
            return True

        if not bar:
            print(_("📥 Compactando {name}...").format(name=self.input_path.name))
            print("-" * 60)
        try:
            if self.compressor == "7z":
                rc, generated_archive = make_7z(
                    str(self.input_path),
                    self.force,
                    threads=self.rar_threads,
                    password=self.rar_password,
                    bar=bar,
                )
            else:
                rc, generated_archive = make_rar(
                    str(self.input_path),
                    self.force,
                    threads=self.rar_threads,
                    password=self.rar_password,
                    bar=bar,
                )

            if not bar:
                print("-" * 60)
            if rc == 0 and generated_archive:
                self.rar_file = generated_archive
                self.input_target = self.rar_file
                return True
            if not bar:
                print(
                    _(
                        "\n❌ Erro ao criar arquivo compactado. Veja o output acima para detalhes. (rc={rc})"
                    ).format(rc=rc)
                )
            return False
        except (FileNotFoundError, PermissionError, OSError) as e:
            if not bar:
                label = (
                    _("binário '{compressor}' não encontrado no PATH").format(
                        compressor=self.compressor
                    )
                    if isinstance(e, FileNotFoundError)
                    else str(e)
                )
                print(_("❌ Erro ao compactar: {label}").format(label=label))
            return False

    def run_makepar(self, bar: Optional[PhaseBar] = None) -> bool:
        if not self.input_target:
            if not bar:
                print(_("Erro: caminho de entrada não definido."))
            return False

        resolver = self._path_resolver()

        if self.skip_par:
            par_path = (
                os.path.join(
                    os.path.dirname(self.input_target),
                    os.path.basename(self.input_target) + ".par2",
                )
                if os.path.isdir(self.input_target)
                else resolver.par_file_path(self.input_target)
            )
            if os.path.exists(par_path):
                self.par_file = par_path
                size_mb = os.path.getsize(self.par_file) / (1024 * 1024)
                if not bar:
                    print(_("✅ Usando paridade existente: {size:.2f} MB").format(size=size_mb))
                return True
            if not bar:
                print(_("❌ Erro: --skip-par mas arquivo {path} não existe.").format(path=par_path))
            return False

        if not bar:
            print("\n" + "=" * 60)
            print(_("🛡️  ETAPA 2: Gerar arquivo de paridade PAR2"))
            print("=" * 60)

        return self._run_makepar_plain(resolver, bar=bar)

    def run_obfuscation(self, bar: Optional[PhaseBar] = None) -> bool:
        if not self.obfuscate:
            return True

        if not bar:
            print("\n" + "=" * 60)
            print(_("🔐 ETAPA 2.5: Ofuscar arquivos"))
            print("=" * 60)
            print(_("🔐 Ofuscando arquivos e ajustando paridade..."))
            print("-" * 60)
        else:
            bar.log(_("🔐 Ofuscando arquivos e ajustando paridade..."))

        assert self.input_target is not None, _("input_target não foi configurado")
        input_target_before = self.input_target

        try:
            # 1. Ofusca arquivos principais
            random_base = generate_random_name()
            obfuscated_path, obf_map, was_linked = perform_obfuscation(
                input_target_before, random_base=random_base
            )

            self.obfuscated_map = obf_map
            self.obfuscate_was_linked = was_linked

            # 2. Renomeia .par2 para nome aleatório (internamente preserva referências reais)
            parent_dir = os.path.dirname(input_target_before)
            is_folder = os.path.isdir(input_target_before)
            is_rar_vol_set = (
                not is_folder
                and input_target_before.endswith(".rar")
                and ".part" in os.path.basename(input_target_before)
            )

            rename_par2_files(parent_dir, input_target_before, is_rar_vol_set, random_base)

            # 3. Deep obfuscation se for pasta
            if is_folder and self.obfuscate:
                self.obfuscated_map.update(deep_obfuscate_tree(obfuscated_path))

            # 4. Atualiza estado do orchestrator
            self.input_target = obfuscated_path
            if self.rar_file:
                self.rar_file = obfuscated_path

            # Atualiza subject para o NZB refletir o nome ofuscado
            obf_basename = os.path.basename(obfuscated_path)
            obf_base_no_ext = re.sub(r"\.part\d+\.rar$", "", obf_basename)
            obf_base_no_ext = re.sub(r"\.rar$", "", obf_base_no_ext)
            self.subject = obf_base_no_ext

            if not bar:
                print(_("✨ Subject ofuscado: {subject}").format(subject=self.subject))
                print("-" * 60)

            self.par_file = self._path_resolver().par_file_path(self.input_target)
            return True

        except Exception as e:
            if not bar:
                print(_("❌ Erro ao ofuscar: {error}").format(error=e))
            return False

    def _run_makepar_plain(self, resolver: PathResolver, bar: Optional[PhaseBar] = None) -> bool:
        if not bar:
            print(_("🔐 Gerando paridade (perfil: {profile})...").format(profile=self.par_profile))
            print("-" * 60)
        assert self.input_target is not None, _("input_target não foi configurado")

        # Se ramdisk foi configurado, o PAR2 será gerado lá
        if self.ramdisk_path:
            base = os.path.basename(self.input_target)
            name_no_ext = base if os.path.isdir(self.input_target) else os.path.splitext(base)[0]
            self.par_file = os.path.join(self.ramdisk_path, name_no_ext + ".par2")
        else:
            self.par_file = (
                os.path.join(
                    os.path.dirname(self.input_target),
                    os.path.basename(self.input_target) + ".par2",
                )
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
                bar=bar,
                output_dir=self.ramdisk_path,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            if not bar:
                label = (
                    _("binário de paridade não encontrado")
                    if isinstance(e, FileNotFoundError)
                    else str(e)
                )
                print(_("❌ Erro ao gerar paridade: {label}").format(label=label))
            return False

        if rc != 0:
            if self.ramdisk_path:
                dev_shm_stat = os.statvfs("/dev/shm")
                available = dev_shm_stat.f_bavail * dev_shm_stat.f_frsize
                estimated_used = self._estimate_par2_size()

                if available < (estimated_used * 0.1):
                    logger.warning(
                        _("Ramdisk possivelmente sem espaço. Retentando com geração em disco...")
                    )
                    if bar:
                        bar.log(_("⚠️ Ramdisk sem espaço. Continuando em disco..."))

                    self._cleanup_ramdisk()
                    self.use_ramdisk = False
                    self.ramdisk_path = None
                    self.force = True

                    self.par_file = (
                        os.path.join(
                            os.path.dirname(self.input_target),
                            os.path.basename(self.input_target) + ".par2",
                        )
                        if os.path.isdir(self.input_target)
                        else resolver.par_file_path(self.input_target)
                    )

                    rc = make_parity(
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
                        dry_run=self.dry_run,
                        bar=bar,
                        output_dir=None,
                    )

                    if rc != 0:
                        if not bar:
                            print("-" * 60)
                            print(
                                _("\n❌ Erro ao gerar paridade em disco (código {rc}).").format(
                                    rc=rc
                                )
                            )
                        assert self.input_target is not None, _("input_target não foi configurado")
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
                            bar=bar,
                        )

                    if not bar:
                        print("-" * 60)
                    return True

            if not bar:
                print("-" * 60)
                print(_("\n❌ Erro ao gerar paridade (código {rc}).").format(rc=rc))
            assert self.input_target is not None, _("input_target não foi configurado")
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
                bar=bar,
            )

        if not bar:
            print("-" * 60)
        return True

    def run_upload(self, bar: Optional[PhaseBar] = None) -> bool:
        if not self.input_target:
            if not bar:
                print(_("Erro: caminho de entrada não definido."))
            return False
        if not bar:
            print("\n" + "=" * 60)
            print(_("📤 ETAPA 3: Upload para Usenet"))
            print("=" * 60)

        try:
            assert self.input_target is not None, _("input_target não foi configurado")
            if self.nzb_conflict:
                self.env_vars["NZB_CONFLICT"] = self.nzb_conflict

            # Resolve NZB uma única vez aqui
            nzb_rel, nzb_abs = resolve_nzb_out(
                self.input_target,
                self.env_vars,
                os.path.isdir(self.input_target),
                self.skip_rar,
                os.path.dirname(self.input_target),
                self.obfuscated_map or None,
            )

            # Trata conflito aqui para saber o caminho final (renomeado se necessário)
            # para o catálogo e TMDb.
            from .nzb import handle_nzb_conflict

            _nzb_rel, nzb_abs, _nzb_overwrite, ok = handle_nzb_conflict(
                nzb_rel, nzb_abs, self.env_vars, working_dir=os.path.dirname(self.input_target)
            )
            if not ok:
                return False

            self.generated_nzb = nzb_abs

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
                resume=self.resume,
                bar=bar,
                nzb_out_abs=self.generated_nzb,
                verify_uploads=self.verify_uploads,
                check_delay=self.check_delay,
                check_retry_delay=self.check_retry_delay,
                check_tries=self.check_tries,
                check_host=self.check_host,
                check_port=self.check_port,
                check_user=self.check_user,
                check_password=self.check_password,
            )
            return rc == 0
        except (FileNotFoundError, PermissionError, OSError) as e:
            if not bar:
                print(_("\n❌ Erro durante upload: {error}").format(error=e))
            return False

    def _do_cleanup(self, on_error: bool = False, preserve_rar: bool = False) -> None:
        do_cleanup_files(self.rar_file, self.par_file, self.keep_files, on_error, preserve_rar)

    def cleanup(self) -> None:
        self._cleanup_par2_symlinks()
        self._cleanup_ramdisk()
        self._do_cleanup(on_error=False)

    def _cleanup_on_error(self, preserve_rar: bool = False) -> None:
        if self._extensionless_map:
            revert_extensionless(self._extensionless_map)
            self._extensionless_map = {}
        self._cleanup_par2_symlinks()
        self._cleanup_ramdisk()
        self._do_cleanup(on_error=True, preserve_rar=preserve_rar)
        self._revert_obfuscation()

    def _revert_extension_normalization(self) -> None:
        if self._extensionless_map:
            revert_extensionless(self._extensionless_map)
            print(
                _("↩️  Restauradas {count} extensões originais").format(
                    count=len(self._extensionless_map)
                )
            )
            self._extensionless_map = {}

    def _revert_obfuscation(self) -> None:
        self.input_target = revert_obfuscation(
            self.obfuscate,
            self.input_target,
            self.input_path,
            self.obfuscate_was_linked,
            self.obfuscated_map,
            self.keep_files,
        )

    def check_nzb_conflict_early(self) -> bool:
        return self._path_resolver().check_nzb_conflict(
            self.input_target, self.skip_upload, self.dry_run
        )

    def _recalculate_resources(self) -> tuple[dict[str, Any], str, str]:
        res, rar_src, par_src = recalculate_resources(
            self.input_path, self._user_rar_threads, self._user_par_threads, self._user_memory_mb
        )
        if self._user_rar_threads is None:
            self.rar_threads = res["threads"]
        if self._user_par_threads is None:
            self.par_threads = res["par_threads"]
        self.par_memory_mb = res["max_memory_mb"]
        return res, rar_src, par_src

    def _estimate_par2_size(self) -> int:
        """
        Estima o tamanho total dos arquivos PAR2 que serão gerados.
        Retorna bytes. Fórmula: tamanho_entrada * (redundância / 100)
        """
        try:
            if not self.input_target:
                return 0
            target = self.input_target
            redundancy = self.redundancy or 10
            total_bytes = 0
            if os.path.isdir(target):
                for root, _, files in os.walk(target):
                    for f in files:
                        total_bytes += os.path.getsize(os.path.join(root, f))
            else:
                total_bytes = os.path.getsize(target)
            par2_estimate = int(total_bytes * (redundancy / 100))
            return max(par2_estimate, 50 * 1024 * 1024)
        except Exception as e:
            logger.warning(_("Não foi possível estimar tamanho PAR2: {e}").format(e=e))
            return 0

    def _setup_ramdisk(self) -> Optional[str]:
        """
        Configura tmpfs em /dev/shm para geração de PAR2.
        Valida espaço disponível vs. estimativa de PAR2.
        Retorna caminho do ramdisk ou None se não houver espaço/falha.
        """
        if not self.use_ramdisk or self.dry_run:
            return None

        try:
            dev_shm = "/dev/shm"
            if not os.path.exists(dev_shm):
                logger.warning(_("/dev/shm não encontrado. Ramdisk desativado."))
                self.use_ramdisk = False
                return None

            stat = os.statvfs(dev_shm)
            available_bytes = stat.f_bavail * stat.f_frsize
            available_gb = available_bytes / (1024**3)

            par2_estimate = self._estimate_par2_size()
            par2_estimate_gb = par2_estimate / (1024**3)

            margin = 0.2
            required_bytes = int(par2_estimate * (1 + margin))

            if available_bytes < required_bytes:
                logger.warning(
                    _(
                        "--use-ramdisk desativado: PAR2 estimado em {est:.1f} GB "
                        "mas há apenas {avail:.1f} GB disponível (mínimo: {req:.1f} GB com margem)"
                    ).format(
                        est=par2_estimate_gb, avail=available_gb, req=required_bytes / (1024**3)
                    )
                )
                self.use_ramdisk = False
                return None

            ramdisk_dir = tempfile.mkdtemp(prefix="upapasta_par2_", dir=dev_shm)
            msg = _(
                "💾 Ramdisk criado em {path} (estimado {est:.1f} GB, {avail:.1f} GB disponível)"
            ).format(path=ramdisk_dir, est=par2_estimate_gb, avail=available_gb)
            logger.info(msg)
            self.ramdisk_path = ramdisk_dir
            return ramdisk_dir
        except OSError as e:
            logger.warning(
                _("Erro ao configurar ramdisk ({e}). Continuando sem ramdisk.").format(e=e)
            )
            self.use_ramdisk = False
            self.ramdisk_path = None
            return None

    def _create_par2_symlinks(self) -> bool:
        """
        Cria symlinks do ramdisk para disco (zero-copy).
        Permite upload/ofuscação ler PAR2 de RAM sem cópia de dados.
        Symlinks transparentes: nyuu lê conteúdo real via link.
        """
        if not self.ramdisk_path or not os.path.exists(self.ramdisk_path):
            return True

        try:
            assert self.input_target is not None, _("input_target não foi configurado")
            input_dir = os.path.dirname(self.input_target)
            base = os.path.basename(self.input_target)
            name_no_ext = base if os.path.isdir(self.input_target) else os.path.splitext(base)[0]

            par2_pattern = os.path.join(self.ramdisk_path, name_no_ext + "*.par2")
            par2_files = glob.glob(par2_pattern)

            if not par2_files:
                logger.warning(
                    _("Nenhum arquivo PAR2 encontrado no ramdisk: {pattern}").format(
                        pattern=par2_pattern
                    )
                )
                return False

            symlink_count = 0
            for src in par2_files:
                dst = os.path.join(input_dir, os.path.basename(src))
                try:
                    if os.path.exists(dst) or os.path.islink(dst):
                        os.remove(dst)
                    os.symlink(src, dst)
                    logger.debug(_("Symlink PAR2: {dst} → {src}").format(dst=dst, src=src))
                    symlink_count += 1
                except Exception as e:
                    logger.warning(
                        _("Falha ao criar symlink PAR2 {dst}: {error}").format(dst=dst, error=e)
                    )
                    return False

            if symlink_count > 0:
                logger.info(
                    _("Criados {count} symlink(s) PAR2 (zero-copy, leitura de RAM)").format(
                        count=symlink_count
                    )
                )
                self.par_file = os.path.join(input_dir, name_no_ext + ".par2")
            return True

        except Exception as e:
            logger.warning(_("Erro ao criar symlinks PAR2 do ramdisk: {error}").format(error=e))
            return False

    def _cleanup_par2_symlinks(self) -> None:
        """Remove symlinks PAR2 criados do ramdisk (após upload completado)."""
        if not self.input_target:
            return

        try:
            input_dir = os.path.dirname(self.input_target)
            base = os.path.basename(self.input_target)
            name_no_ext = base if os.path.isdir(self.input_target) else os.path.splitext(base)[0]

            par2_pattern = os.path.join(input_dir, name_no_ext + "*.par2")
            for par2_file in glob.glob(par2_pattern):
                if os.path.islink(par2_file):
                    target = os.readlink(par2_file)
                    if self.ramdisk_path and self.ramdisk_path in target:
                        try:
                            os.remove(par2_file)
                            logger.debug(_("Symlink PAR2 removido: {f}").format(f=par2_file))
                        except Exception as e:
                            logger.warning(
                                _("Falha ao remover symlink {f}: {error}").format(
                                    f=par2_file, error=e
                                )
                            )
        except Exception as e:
            logger.debug(_("Erro ao limpar symlinks PAR2: {error}").format(error=e))

    def _cleanup_ramdisk(self) -> None:
        """Remove o ramdisk temporário se foi criado."""
        if self.ramdisk_path and os.path.exists(self.ramdisk_path):
            try:
                shutil.rmtree(self.ramdisk_path)
                logger.debug(_("Ramdisk removido: {path}").format(path=self.ramdisk_path))
            except Exception as e:
                logger.warning(_("Falha ao remover ramdisk: {error}").format(error=e))
            finally:
                self.ramdisk_path = None

    def run(self) -> int:
        total_start = time.time()

        from .config import load_env_file

        self.env_vars = load_env_file(self.env_file)

        if not self.skip_upload:
            self.env_vars = check_or_prompt_credentials(self.env_file)
            if not self.env_vars:
                return 3

        if not self.validate():
            return 1

        res, rar_src, par_src = self._recalculate_resources()
        nntp_connections = int(
            self.env_vars.get("NNTP_CONNECTIONS") or os.environ.get("NNTP_CONNECTIONS", "10")
        )
        total_bytes = get_total_size(str(self.input_path))
        eta_s = int(total_bytes / (nntp_connections * 500 * 1024))
        eta_str = format_time(eta_s) if eta_s > 0 else _("N/A")

        PipelineReporter.print_header(
            self.input_path,
            res,
            self.subject,
            self.par_profile,
            self.post_size,
            self.rar_threads,
            self.par_threads,
            rar_src,
            par_src,
            self.obfuscate,
            self.rar_password,
            self.dry_run,
            eta_str,
            nntp_connections,
        )

        meta = {
            "size": res["total_gb"],
            "obfuscate": self.obfuscate,
            "password": self.rar_password,
        }

        with PhaseBar(metadata=meta) as bar:
            single_file_no_rar = (
                self.input_path.is_file()
                and self.skip_rar
                and not self.obfuscate
                and not self.rar_password
            )
            if self.skip_rar or single_file_no_rar:
                bar.skip("PACK")
            if self.skip_par:
                bar.skip("PAR2")
            if not self.obfuscate:
                bar.skip("OBF")
            if self.skip_upload:
                bar.skip("UPLOAD")

            # ── NFO ──────────────────────────────────────────────────────────────
            if not self.dry_run:
                bar.start("NFO")
                if not self.run_generate_nfo(bar=bar):
                    bar.skip("NFO")
                else:
                    bar.log(_("Arquivo NFO gerado com sucesso."))
                    bar.done("NFO")
            else:
                bar.skip("NFO")

            if not self.check_nzb_conflict_early():
                return 3

            # ── COMPRESSION ──────────────────────────────────────────────────────
            will_create_rar = not self.skip_rar
            if will_create_rar:
                bar.start("PACK")
                if not self.run_compression(bar=bar):
                    bar.error("PACK")
                    self._cleanup_on_error()
                    return 1
                bar.log(_("Arquivo compactado criado com sucesso."))
                bar.done("PACK")
            else:
                if not self.run_compression(bar=bar):
                    self._cleanup_on_error()
                    return 1

            # ── Normalização de extensões ────────────────────────────────────────
            if self.rename_extensionless and self.skip_rar and not self.dry_run:
                target = self.input_target or str(self.input_path)
                self._extensionless_map = normalize_extensionless(target)

            # ── PAR2 ─────────────────────────────────────────────────────────────
            if self.use_ramdisk and not self.skip_par:
                bar.log(_("💾 Configurando ramdisk para PAR2 (zero-copy)..."))
                self._setup_ramdisk()

            if not self.skip_par:
                bar.start("PAR2")
                if not self.run_makepar(bar=bar):
                    bar.error("PAR2")
                    self._cleanup_on_error(preserve_rar=True)
                    return 2
                bar.log(_("Arquivos de paridade criados com sucesso."))
                bar.done("PAR2")
            else:
                if not self.run_makepar(bar=bar):
                    self._cleanup_on_error()
                    return 2

            # ── SYMLINKS DO RAMDISK (zero-copy) ─────────────────────────────────
            if self.ramdisk_path and (self.obfuscate or not self.skip_upload):
                if not self._create_par2_symlinks():
                    bar.error("PAR2")
                    self._cleanup_on_error()
                    return 2

            # ── OBFUSCATION ──────────────────────────────────────────────────────
            if self.obfuscate and not self.dry_run:
                bar.start("OBF")
                if not self.run_obfuscation(bar=bar):
                    bar.error("OBF")
                    self._cleanup_on_error()
                    return 1
                bar.log(_("Arquivos ofuscados com sucesso."))
                bar.done("OBF")
            else:
                bar.skip("OBF")

            stats = PipelineReporter.collect_stats(self.input_target, self.rar_file, self.par_file)

            # ── Upload ───────────────────────────────────────────────────────────
            if not self.skip_upload:
                bar.start("UPLOAD")
                if not self.run_upload(bar=bar):
                    bar.error("UPLOAD")
                    self._cleanup_on_error()
                    return 3

                # F3.5: Enriquecimento de metadados no NZB
                if self.generated_nzb and self.tmdb_data:
                    enrich_nzb_metadata(self.generated_nzb, self.tmdb_data)
                    bar.log(_("Metadados TMDb injetados no NZB."))

                bar.log(_("Upload concluído para Usenet."))
                bar.done("UPLOAD")
                self.cleanup()
                self._revert_extension_normalization()
                self._revert_obfuscation()
            else:
                self._revert_extension_normalization()
                self._revert_obfuscation()

            total_elapsed = time.time() - total_start
            bar.done("DONE")

        PipelineReporter.print_summary(
            stats,
            self.input_path,
            self.subject,
            self.rar_password,
            self.obfuscate,
            self.skip_upload,
            self.env_vars,
            self.group,
            self.nfo_file,
            self.rar_file,
            total_elapsed,
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
            tmdb_id=self.tmdb_id or (self.tmdb_data.get("id") if self.tmdb_data else None),
            compressor=self.compressor if not self.skip_rar else None,
        )

        return 0
