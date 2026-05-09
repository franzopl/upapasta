"""
_pipeline.py

Classes auxiliares do UpaPastaOrchestrator:
  - DependencyChecker  : valida entrada, permissões e disco
  - PathResolver       : resolve caminhos NZB/NFO/PAR2
  - PipelineReporter   : banner, estatísticas, sumário e catálogo

Funções auxiliares standalone:
  - normalize_extensionless / revert_extensionless
  - do_cleanup_files        : remove RAR e PAR2 gerados
  - revert_obfuscation      : restaura nomes originais ou remove hardlinks
  - recalculate_resources   : dimensiona threads/memória para a entrada
"""

from __future__ import annotations

import glob
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from .i18n import _
from .resources import calculate_optimal_resources, get_total_size

# ── Funções utilitárias de extensão (re-exportadas por orchestrator) ─────────


def normalize_extensionless(root: str, suffix: str = ".bin") -> dict[str, str]:
    """Renomeia recursivamente arquivos sem extensão para `<nome>{suffix}`.

    Mitigação para SABnzbd com "Unwanted Extensions": arquivos sem extensão
    recebem .txt no destino, quebrando hashes e estrutura.

    Retorna dict {novo_caminho_absoluto: caminho_original_absoluto}.
    """
    mapping: dict[str, str] = {}

    def _rename_one(path: str) -> None:
        base = os.path.basename(path)
        if "." in base and not base.startswith(".") and os.path.splitext(base)[1]:
            return
        if base.startswith("."):
            return
        new = path + suffix
        if os.path.exists(new):
            return
        os.replace(path, new)
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
                os.replace(new_path, original)
            except OSError:
                pass


# ── DependencyChecker ─────────────────────────────────────────────────────────


class DependencyChecker:
    """Valida a entrada e o ambiente antes de iniciar o pipeline."""

    @staticmethod
    def validate(input_path: Path, dry_run: bool) -> bool:
        """Verifica existência, permissões de leitura e espaço em disco."""
        if not input_path.exists():
            print(
                _("Erro: arquivo ou pasta '{input_path}' não existe.").format(input_path=input_path)
            )
            return False

        if not input_path.is_dir() and not input_path.is_file():
            print(
                _("Erro: '{input_path}' não é um arquivo nem um diretório.").format(
                    input_path=input_path
                )
            )
            return False

        unreadable = []
        if input_path.is_file():
            if not os.access(str(input_path), os.R_OK):
                unreadable.append(str(input_path))
        else:
            for dirpath, _dirs, files in os.walk(str(input_path)):
                for f in files:
                    fp = os.path.join(dirpath, f)
                    if not os.access(fp, os.R_OK):
                        unreadable.append(fp)
        if unreadable:
            print(
                _("Erro: {count} arquivo(s) sem permissão de leitura:").format(
                    count=len(unreadable)
                )
            )
            for p in unreadable[:5]:
                print(_("  {p}").format(p=p))
            if len(unreadable) > 5:
                print(_("  ... e mais {count}").format(count=len(unreadable) - 5))
            return False

        if not dry_run:
            source_size = get_total_size(str(input_path))
            try:
                stat = shutil.disk_usage(str(input_path.parent))
                needed = source_size * 2
                if stat.free < needed:
                    free_gb = stat.free / (1024**3)
                    needed_gb = needed / (1024**3)
                    source_gb = source_size / (1024**3)
                    print(
                        _(
                            "Erro: espaço insuficiente em disco.\n"
                            "  Fonte: {source_gb:.2f} GB | Necessário (2×): {needed_gb:.2f} GB | Livre: {free_gb:.2f} GB\n"
                            "  Libere espaço ou use --dry-run para simular."
                        ).format(source_gb=source_gb, needed_gb=needed_gb, free_gb=free_gb)
                    )
                    return False
            except OSError:
                pass

        return True


# ── PathResolver ──────────────────────────────────────────────────────────────


class PathResolver:
    """Resolve caminhos de saída para NZB, NFO e PAR2."""

    def __init__(
        self,
        env_vars: dict[str, str],
        input_path: Path,
        skip_rar: bool,
        nzb_conflict: Optional[str],
        subject: str,
    ) -> None:
        self.env_vars = env_vars
        self.input_path = input_path
        self.skip_rar = skip_rar
        self.nzb_conflict = nzb_conflict
        self.subject = subject

    def _effective_env(self) -> dict[str, str]:
        env = self.env_vars.copy()
        if self.nzb_conflict:
            env["NZB_CONFLICT"] = self.nzb_conflict
        return env

    def nfo_path(self) -> tuple[str, str]:
        """Retorna (nfo_path_absoluto, nzb_dir)."""
        from .config import render_template
        from .nzb import resolve_nzb_template

        env = self._effective_env()
        nzb_template = resolve_nzb_template(env, self.input_path.is_dir(), self.skip_rar)

        basename = self.subject
        video_exts = (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm")
        if basename.lower().endswith(video_exts):
            basename = os.path.splitext(basename)[0]

        nzb_filename = render_template(nzb_template, basename)

        if os.path.isabs(nzb_filename):
            nzb_dir = os.path.dirname(nzb_filename)
            nfo_filename = os.path.splitext(os.path.basename(nzb_filename))[0] + ".nfo"
        else:
            nzb_dir = env.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
            nfo_filename = os.path.splitext(nzb_filename)[0] + ".nfo"

        return os.path.join(nzb_dir, nfo_filename), nzb_dir

    @staticmethod
    def par_file_path(input_target: str) -> str:
        """Retorna o caminho esperado do .par2 para input_target."""
        stem = os.path.splitext(input_target)[0]
        if input_target.endswith(".rar") and ".part" in stem:
            stem = stem.rsplit(".part", 1)[0]
        elif input_target.endswith(".001") and ".7z." in input_target:
            stem = input_target.rsplit(".7z.", 1)[0]
        return stem + ".par2"

    def check_nzb_conflict(
        self,
        input_target: Optional[str],
        skip_upload: bool,
        dry_run: bool,
    ) -> bool:
        """Verifica conflito de NZB antecipadamente."""
        from .nzb import handle_nzb_conflict, resolve_nzb_out

        if skip_upload or dry_run:
            return True

        path = input_target or str(self.input_path)
        is_folder = os.path.isdir(path)
        env = self._effective_env()
        working_dir = env.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
        nzb_out, nzb_out_abs = resolve_nzb_out(path, env, is_folder, self.skip_rar, working_dir)
        _, _, _, ok = handle_nzb_conflict(nzb_out, nzb_out_abs, env)
        return ok


# ── PipelineReporter ──────────────────────────────────────────────────────────


class PipelineReporter:
    """Formata e exibe o progresso, resultado e catálogo do pipeline."""

    @staticmethod
    def print_header(
        input_path: Path,
        res: dict[str, Any],
        subject: str,
        par_profile: str,
        post_size: Optional[str],
        rar_threads: int,
        par_threads: int,
        rar_src: str,
        par_src: str,
        obfuscate: bool,
        rar_password: Optional[str],
        dry_run: bool,
        eta_str: str,
        nntp_connections: int,
    ) -> None:
        print("\n" + "=" * 60)
        print(_("🚀 UpaPasta — Preparando Upload para Usenet"))
        print("=" * 60)
        print(_("📁 Entrada:     {name}").format(name=input_path.name))
        print(
            _("⏱  ETA upload:  ~{eta} @ {conn} conexões").format(eta=eta_str, conn=nntp_connections)
        )
        print(_("✉️  Subject:     {subject}").format(subject=subject))
        if dry_run:
            print(_("⚠️  [DRY-RUN] Modo de simulação ativado"))
        print("-" * 60)

    @staticmethod
    def collect_stats(
        input_target: Optional[str],
        rar_file: Optional[str],
        par_file: Optional[str],
    ) -> dict[str, float | int]:
        """Coleta tamanhos de arquivos compactados e PAR2 gerados."""
        stats: dict[str, float | int] = {
            "archive_size_mb": 0.0,
            "par2_size_mb": 0.0,
            "par2_file_count": 0,
        }
        if not input_target or not os.path.exists(input_target):
            return stats

        base_name: str
        if os.path.isdir(input_target):
            total_bytes = 0
            for root, _dirs, files in os.walk(input_target):
                for file in files:
                    try:
                        total_bytes += os.path.getsize(os.path.join(root, file))
                    except OSError:
                        pass
            stats["archive_size_mb"] = total_bytes / (1024 * 1024)
            base_name = input_target
        else:
            try:
                # Detecta se é RAR ou 7z para encontrar volumes
                if input_target.endswith(".rar") or ".part" in input_target:
                    stem = re.sub(r"\.part\d+$", "", os.path.splitext(input_target)[0])
                    vols = glob.glob(glob.escape(stem) + ".part*.rar")
                elif input_target.endswith((".7z", ".7z.001")):
                    stem = re.sub(r"\.7z\.\d+$", "", input_target)
                    if stem.endswith(".7z"):
                        stem = stem[:-3]
                    vols = glob.glob(glob.escape(stem) + ".7z.[0-9][0-9][0-9]")
                else:
                    vols = []

                if vols:
                    stats["archive_size_mb"] = sum(os.path.getsize(f) for f in vols) / (1024 * 1024)
                    base_name = stem
                else:
                    stats["archive_size_mb"] = os.path.getsize(input_target) / (1024 * 1024)
                    base_name = os.path.splitext(input_target)[0]
            except OSError:
                base_name = os.path.splitext(input_target)[0]

        par_volumes = glob.glob(glob.escape(base_name) + "*.par2")
        stats["par2_file_count"] = len(par_volumes)
        stats["par2_size_mb"] = sum(
            os.path.getsize(f) for f in par_volumes if os.path.exists(f)
        ) / (1024 * 1024)
        return stats

    @staticmethod
    def print_summary(
        stats: dict[str, float | int],
        input_path: Path,
        subject: str,
        rar_password: Optional[str],
        obfuscate: bool,
        skip_upload: bool,
        env_vars: dict[str, str],
        group: Optional[str],
        nfo_file: Optional[str],
        rar_file: Optional[str],
        elapsed: float,
    ) -> None:
        from .ui import format_time

        print("=" * 60)
        print(_("✨ WORKFLOW CONCLUÍDO COM SUCESSO!"))
        print("=" * 60)

        if obfuscate:
            print(_("  » Nome Ofuscado:    [bold cyan]{subject}[/]").format(subject=subject))
        if rar_password:
            print(
                _("  » Senha RAR:        [bold yellow]{password}[/]").format(password=rar_password)
            )

        if not skip_upload:
            raw_group = group or env_vars.get("USENET_GROUP") or _("(Não especificado)")
            display_group = (
                _("Pool ({count} grupos)").format(count=len(raw_group.split(",")))
                if "," in raw_group
                else raw_group
            )
            print(_("  » Grupo Usenet:     {group}").format(group=display_group))

        print(_("\n📦 ARQUIVOS GERADOS:"))
        if nfo_file and os.path.exists(nfo_file):
            print(_("  • NFO: {name}").format(name=os.path.basename(nfo_file)))

        rar_display = os.path.basename(rar_file) if rar_file else None
        if stats["archive_size_mb"] > 0:
            name = rar_display or input_path.name
            label = "7z" if name.lower().endswith((".7z", ".001")) else "RAR"
            print(
                _("  • {label}: {name} ({size:.2f} MB)").format(
                    label=label, name=name, size=stats["archive_size_mb"]
                )
            )

        if stats["par2_file_count"] > 0:
            print(
                _("  • PAR2: {count} arquivo(s) ({size:.2f} MB)").format(
                    count=stats["par2_file_count"], size=stats["par2_size_mb"]
                )
            )

        total_size = stats["archive_size_mb"] + stats["par2_size_mb"]
        print(_("  • Total: {size:.2f} MB").format(size=total_size))

        print(_("\n⏱️  Tempo total: {time}").format(time=format_time(int(elapsed))))
        print("=" * 60 + "\n")

    @staticmethod
    def record_catalog_and_hook(
        env_vars: dict[str, str],
        stats: dict[str, float | int],
        input_path: Path,
        subject: str,
        rar_password: Optional[str],
        obfuscate: bool,
        skip_upload: bool,
        group: Optional[str],
        nfo_file: Optional[str],
        elapsed: float,
        skip_rar: bool,
        obfuscated_map: dict[str, str],
        redundancy: Optional[int],
        nzb_path: Optional[str],
    ) -> None:
        from .catalog import record_upload, run_post_upload_hook
        from .nzb import resolve_nzb_out

        working_dir = env_vars.get("NZB_OUT_DIR") or os.environ.get("NZB_OUT_DIR") or os.getcwd()
        nzb_out, _nzb_abs = resolve_nzb_out(
            str(input_path), env_vars, input_path.is_dir(), skip_rar, working_dir, obfuscated_map
        )

        _nzb_abs_final: Optional[str] = _nzb_abs
        if _nzb_abs and not os.path.exists(_nzb_abs):
            base, ext = os.path.splitext(_nzb_abs)
            for i in range(1, 11):
                test_path = f"{base}_{i}{ext}"
                if os.path.exists(test_path):
                    _nzb_abs_final = test_path
                    break
            else:
                _nzb_abs_final = None

        raw_group = group or env_vars.get("USENET_GROUP") or ""
        effective_group = raw_group.split(",")[0].strip() if "," in raw_group else raw_group

        tamanho = int(stats["archive_size_mb"] * 1024 * 1024) if stats["archive_size_mb"] else None
        nome_ofuscado = subject if obfuscate else None

        try:
            record_upload(
                nome_original=input_path.name,
                nome_ofuscado=nome_ofuscado,
                senha_rar=rar_password,
                tamanho_bytes=tamanho,
                grupo_usenet=effective_group or None,
                servidor_nntp=env_vars.get("NNTP_HOST") or os.environ.get("NNTP_HOST"),
                redundancia_par2=f"{redundancy}%" if redundancy else None,
                duracao_upload_s=round(elapsed, 1),
                num_arquivos_rar=int(stats["par2_file_count"])
                if "par2_file_count" in stats
                else None,
                caminho_nzb=_nzb_abs_final,
                subject=subject,
            )
        except Exception as e:
            print(_("⚠️  Falha ao registrar no catálogo: {error}").format(error=e))

        if not skip_upload:
            run_post_upload_hook(
                env_vars,
                nzb_path=_nzb_abs_final,
                nfo_path=nfo_file,
                senha_rar=rar_password,
                nome_original=input_path.name,
                nome_ofuscado=nome_ofuscado,
                tamanho_bytes=tamanho,
                grupo_usenet=effective_group or None,
            )

            webhook_url = env_vars.get("WEBHOOK_URL") or os.environ.get("WEBHOOK_URL")
            if webhook_url:
                from ._webhook import send_webhook
                from .catalog import detect_category

                categoria = detect_category(input_path.name)
                send_webhook(
                    webhook_url,
                    input_path.name,
                    tamanho_bytes=tamanho,
                    grupo=effective_group or None,
                    categoria=categoria,
                )


# ── Funções auxiliares standalone ────────────────────────────────────────────


def do_cleanup_files(
    rar_file: Optional[str],
    par_file: Optional[str],
    keep_files: bool,
    on_error: bool = False,
    preserve_rar: bool = False,
) -> None:
    """Remove arquivos RAR e PAR2 gerados pelo pipeline."""
    if keep_files and not on_error:
        print(_("\n⚡ [--keep-files] Mantendo arquivos RAR e PAR2."))
        return

    candidates: list[str] = []
    base_name: Optional[str] = None

    if rar_file and not preserve_rar:
        # RAR volumes: .part01.rar
        rar_base = re.sub(r"\.part\d+$", "", os.path.splitext(rar_file)[0])
        rar_volumes = glob.glob(glob.escape(rar_base) + ".part*.rar")

        # 7z volumes: .7z.001
        sz_base = re.sub(r"\.7z\.\d+$", "", rar_file)
        if sz_base.endswith(".7z"):
            sz_base = sz_base[:-3]
        sz_volumes = glob.glob(glob.escape(sz_base) + ".7z.[0-9][0-9][0-9]")

        candidates.extend(rar_volumes if rar_volumes else [])
        candidates.extend(sz_volumes if sz_volumes else [])
        if not rar_volumes and not sz_volumes and os.path.exists(rar_file):
            candidates.append(rar_file)

        base_name = (
            rar_base if rar_volumes else (sz_base if sz_volumes else os.path.splitext(rar_file)[0])
        )
    elif rar_file and preserve_rar:
        # Para encontrar o .par2 mesmo se preservarmos o RAR
        base_name = re.sub(r"\.part\d+$", "", os.path.splitext(rar_file)[0])
        if rar_file.endswith((".7z", ".001")):
            sz_base = re.sub(r"\.7z\.\d+$", "", rar_file)
            if sz_base.endswith(".7z"):
                sz_base = sz_base[:-3]
            base_name = sz_base

    if base_name is None and par_file:
        base_name = os.path.splitext(par_file)[0]
    if base_name:
        candidates.extend(glob.glob(glob.escape(base_name) + "*.par2"))
    elif par_file and os.path.exists(par_file):
        candidates.append(par_file)

    files_to_delete = list(dict.fromkeys(candidates))
    deleted_count = 0

    if files_to_delete:
        if on_error:
            print(_("\n🧹 Limpando arquivos temporários devido a erro..."))
        else:
            print(
                _("\n🧹 Limpando {count} arquivo(s) temporário(s)...").format(
                    count=len(files_to_delete)
                ),
                end=" ",
                flush=True,
            )

    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                deleted_count += 1
        except Exception:
            pass

    if deleted_count > 0 and not on_error:
        print(_("✅ Concluído"))
    elif deleted_count > 0 and on_error:
        print(_("✅ {count} arquivo(s) removidos.").format(count=deleted_count))
    print()


def revert_obfuscation(
    obfuscate: bool,
    input_target: Optional[str],
    input_path: Path,
    obfuscate_was_linked: bool,
    obfuscated_map: dict[str, str],
    keep_files: bool,
) -> Optional[str]:
    """
    Restaura o nome original da entrada ou remove hardlinks.

    Retorna o novo input_target (que pode ter sido restaurado ao original).
    """
    if not obfuscate or not input_target:
        return input_target

    original = str(input_path)
    if input_target == original:
        return input_target

    if obfuscate_was_linked:
        if keep_files:
            print(
                _("⚡ [--keep-files] Mantendo links de ofuscação: {name}").format(
                    name=os.path.basename(input_target)
                )
            )
            return input_target
        if not os.path.exists(input_target):
            # hardlink já removido pelo cleanup; o original (mesmo inode) pode ainda existir
            target_dir = os.path.dirname(input_target)
            target_ext = os.path.splitext(input_target)[1]
            obf_full_base = os.path.basename(os.path.splitext(input_target)[0])
            obf_base = re.sub(r"\.part\d+$", "", obf_full_base)
            original_base = obfuscated_map.get(obf_base)
            if original_base:
                # arquivo único ou primeiro volume
                orig_path = os.path.join(target_dir, original_base + target_ext)
                candidates = glob.glob(
                    glob.escape(os.path.join(target_dir, original_base)) + ".part*.rar"
                )
                sz_candidates = glob.glob(
                    glob.escape(os.path.join(target_dir, original_base)) + ".7z.[0-9][0-9][0-9]"
                )
                candidates.extend(sz_candidates)

                if not candidates and os.path.exists(orig_path):
                    candidates = [orig_path]
                for cand in candidates:
                    try:
                        os.remove(cand)
                        print(
                            _("🧹 Removido original após cleanup do hardlink: {name}").format(
                                name=os.path.basename(cand)
                            )
                        )
                    except OSError as e:
                        print(
                            _("⚠️  Falha ao remover original '{name}': {error}").format(
                                name=os.path.basename(cand), error=e
                            )
                        )
            return input_target
        print(
            _("🧹 Removendo links temporários de ofuscação: {name}").format(
                name=os.path.basename(input_target)
            )
        )
        try:
            if os.path.isdir(input_target):
                shutil.rmtree(input_target)
            else:
                os.remove(input_target)
        except OSError as e:
            print(_("⚠️  Falha ao remover links de ofuscação: {error}").format(error=e))
        return input_target

    if not os.path.exists(input_target) or os.path.exists(original):
        return input_target
    try:
        os.replace(input_target, original)
        print(_("↩️  Nome original restaurado: {name}").format(name=input_path.name))
        input_target = original
    except OSError as e:
        print(
            _("⚠️  Falha ao restaurar nome original ('{input}' → '{original}'): {error}").format(
                input=input_target, original=original, error=e
            )
        )
        print(
            _("    AÇÃO MANUAL: renomeie '{input}' de volta para '{original}'").format(
                input=os.path.basename(input_target), original=input_path.name
            )
        )
        return input_target

    obf_base = os.path.basename(input_target)
    deep_entries = {k: v for k, v in obfuscated_map.items() if k != obf_base}
    for new_rel in sorted(deep_entries, key=lambda p: p.count(os.sep), reverse=True):
        orig_rel = deep_entries[new_rel]
        new_full = os.path.join(original, new_rel)
        orig_full = os.path.join(original, orig_rel)
        if os.path.exists(new_full) and not os.path.exists(orig_full):
            try:
                os.makedirs(os.path.dirname(orig_full), exist_ok=True)
                os.replace(new_full, orig_full)
            except OSError:
                pass
    return input_target


def print_skip_rar_hints(input_path: Path, filepath_format: str, backend: str) -> None:
    """Exibe dicas relevantes quando skip_rar está ativo."""
    if not input_path.is_dir():
        return
    if backend == "parpar":
        has_subdirs = any(e.is_dir() for e in input_path.iterdir())
        if has_subdirs:
            print(
                _(
                    "✅ Pasta com subpastas + parpar (filepath-format={fmt}): "
                    "estrutura será preservada via PAR2."
                ).format(fmt=filepath_format)
            )
            print(
                _(
                    "   Dica: no SABnzbd, desative 'Recursive Unpacking' para preservar .zip internos\n"
                    "   e revise 'Unwanted Extensions' (use --rename-extensionless se houver arquivos sem extensão)."
                )
            )
            empty_dirs = [
                os.path.relpath(dp, input_path)
                for dp, _d, files in os.walk(input_path)
                if not files and dp != str(input_path) and not any(os.scandir(dp))
            ]
            if empty_dirs:
                print(
                    _(
                        "⚠️  {count} diretório(s) vazio(s) detectado(s) — não serão preservados no upload.\n"
                        "    Usenet posta artigos (arquivos), não diretórios; pastas vazias somem no destino.\n"
                        "    Se a estrutura vazia for relevante, remova --skip-rar para empacotar em RAR."
                    ).format(count=len(empty_dirs))
                )
    elif backend == "par2":
        print(
            _(
                "⚠️  Backend par2 + --skip-rar com pasta: par2 clássico não preserva hierarquia.\n"
                "    Considere --backend parpar (recomendado) ou remova --skip-rar."
            )
        )


def print_rar_hints(
    input_path: Path, backend: str, rar_password: Optional[str], obfuscate: bool
) -> None:
    """Exibe dica sobre skip-rar quando RAR é desnecessário."""
    if (
        input_path.is_dir()
        and backend == "parpar"
        and not rar_password
        and not obfuscate
        and any(e.is_dir() for e in input_path.iterdir())
    ):
        print(
            _(
                "💡 Dica: para esta pasta com subpastas, considere --skip-rar.\n"
                "   parpar preserva a hierarquia nos .par2 (filepath-format=common) e\n"
                "   downloaders modernos reconstroem a árvore. Menos overhead, mesmo resultado."
            )
        )


def recalculate_resources(
    input_path: Path,
    user_rar_threads: Optional[int],
    user_par_threads: Optional[int],
    user_memory_mb: Optional[int],
) -> tuple[dict[str, Any], str, str]:
    """Recalcula threads e memória ótimos baseados no tamanho real da entrada."""
    total_bytes = get_total_size(str(input_path))
    res = calculate_optimal_resources(
        total_bytes,
        user_threads=user_rar_threads if user_rar_threads == user_par_threads else None,
        user_memory_mb=user_memory_mb,
    )
    conservative_tag = _(" (conservador)") if res["conservative_mode"] else ""
    rar_src = _("manual") if user_rar_threads is not None else f"auto{conservative_tag}"
    par_src = _("manual") if user_par_threads is not None else f"auto{conservative_tag}"
    return res, rar_src, par_src
