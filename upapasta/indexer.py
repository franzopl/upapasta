"""
indexer.py

Busca em indexadores compatíveis com o protocolo Newznab (incluindo Prowlarr)
antes de fazer upload — se o conteúdo já está na Usenet, baixa só o .nzb
como backup local e pula o upload. Zero downloads de conteúdo.

Rate limiting embutido + cache JSONL local com TTL configurável.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree

from .config import CONFIG_DIR

INDEXER_CACHE_FILE = os.path.join(CONFIG_DIR, "indexer_cache.jsonl")
INDEXER_NZB_DIR = os.path.join(CONFIG_DIR, "nzb", "indexer")

_DEFAULT_RATE_SECS = 2.0
_DEFAULT_CACHE_DAYS = 30
_LAST_REQUEST: dict[str, float] = {}


@dataclass
class IndexerResult:
    title: str
    guid: str
    nzb_url: str
    size: int = 0
    pub_date: str = ""
    indexer: str = ""
    grabs: int = 0


@dataclass
class _CacheEntry:
    query: str
    indexer_url: str
    ts: float
    found: bool
    results: list[dict[str, str]] = field(default_factory=list)


# ── Cache JSONL ──────────────────────────────────────────────────────────────


def _cache_key(query: str, indexer_url: str) -> tuple[str, str]:
    return query.lower().strip(), indexer_url.rstrip("/").lower()


def _load_cache(max_age_days: int = _DEFAULT_CACHE_DAYS) -> dict[tuple[str, str], _CacheEntry]:
    cache: dict[tuple[str, str], _CacheEntry] = {}
    if not os.path.exists(INDEXER_CACHE_FILE):
        return cache
    cutoff = time.time() - max_age_days * 86400
    with open(INDEXER_CACHE_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                entry = _CacheEntry(
                    query=obj["query"],
                    indexer_url=obj["indexer_url"],
                    ts=float(obj["ts"]),
                    found=bool(obj["found"]),
                    results=obj.get("results", []),
                )
                if entry.ts >= cutoff:
                    key = _cache_key(entry.query, entry.indexer_url)
                    cache[key] = entry
            except (KeyError, ValueError, json.JSONDecodeError):
                pass
    return cache


def _save_entry(entry: _CacheEntry) -> None:
    os.makedirs(os.path.dirname(INDEXER_CACHE_FILE), exist_ok=True)
    with open(INDEXER_CACHE_FILE, "a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "query": entry.query,
                    "indexer_url": entry.indexer_url,
                    "ts": entry.ts,
                    "found": entry.found,
                    "results": entry.results,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _compact_cache(max_age_days: int = _DEFAULT_CACHE_DAYS) -> None:
    """Reescreve o cache mantendo apenas entradas dentro do TTL (uma por chave)."""
    cache = _load_cache(max_age_days)
    if not cache:
        if os.path.exists(INDEXER_CACHE_FILE):
            os.remove(INDEXER_CACHE_FILE)
        return
    os.makedirs(os.path.dirname(INDEXER_CACHE_FILE), exist_ok=True)
    with open(INDEXER_CACHE_FILE, "w", encoding="utf-8") as fh:
        for entry in cache.values():
            fh.write(
                json.dumps(
                    {
                        "query": entry.query,
                        "indexer_url": entry.indexer_url,
                        "ts": entry.ts,
                        "found": entry.found,
                        "results": entry.results,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ── Query normalization ──────────────────────────────────────────────────────

_NOISE = re.compile(
    r"[\.\-_]"
    r"|(?<!\w)\d{4}(?!\w)"  # ano isolado
    r"|\b(PROPER|REPACK|REMASTERED|EXTENDED|UNRATED|DC)\b"
    r"|\b(BluRay|BDRip|WEB-?DL|WEBRip|HDRip|DVDRip|HDTV|PDTV)\b"
    r"|\b(x264|x265|HEVC|AVC|H264|H265|AAC|AC3|DTS|MP3)\b"
    r"|\b(1080p|720p|2160p|4K|UHD|SD|480p)\b",
    re.IGNORECASE,
)


def normalize_query(name: str) -> str:
    """Limpa nome de arquivo/pasta para query de busca."""
    # Remove extensão se for arquivo
    base = os.path.splitext(name)[0]
    q = _NOISE.sub(" ", base)
    # Colapsa espaços
    q = re.sub(r"\s+", " ", q).strip()
    return q


# ── Rate limiting ────────────────────────────────────────────────────────────


def _rate_limit(indexer_url: str, min_interval: float) -> None:
    key = indexer_url.rstrip("/").lower()
    last = _LAST_REQUEST.get(key, 0.0)
    elapsed = time.time() - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _LAST_REQUEST[key] = time.time()


# ── HTTP helpers ─────────────────────────────────────────────────────────────


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "UpaPasta/0.31 (Newznab client)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: bytes = resp.read()
    return data


def _extract_rate_limit(headers: object) -> Optional[float]:
    """Lê X-RateLimit-Remaining / X-RateLimit-Reset se disponíveis."""
    try:
        remaining = int(headers["X-RateLimit-Remaining"])  # type: ignore[index]
        reset = int(headers["X-RateLimit-Reset"])  # type: ignore[index]
        if remaining <= 1:
            wait = max(0, reset - int(time.time())) + 1
            return float(wait)
    except (TypeError, KeyError, ValueError):
        pass
    return None


# ── Newznab parser ───────────────────────────────────────────────────────────

_NEWZNAB_NS = "http://www.newznab.com/DTD/2010/feeds/attributes/"


def _parse_newznab_json(data: bytes, indexer_url: str) -> list[IndexerResult]:
    """Parseia resposta JSON do Newznab (o=json)."""
    obj = json.loads(data.decode("utf-8", errors="replace"))
    items = obj.get("item") or obj.get("channel", {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    results = []
    for it in items:
        nzb_url = it.get("link", "")
        if not nzb_url:
            enclosure = it.get("enclosure", {})
            nzb_url = enclosure.get("@url") or enclosure.get("url", "")
        try:
            size = int(it.get("size") or it.get("enclosure", {}).get("@length", 0))
        except (ValueError, TypeError):
            size = 0
        results.append(
            IndexerResult(
                title=it.get("title", ""),
                guid=it.get("guid", ""),
                nzb_url=nzb_url,
                size=size,
                pub_date=it.get("pubDate", ""),
                indexer=indexer_url,
                grabs=int(it.get("grabs", 0) or 0),
            )
        )
    return results


def _parse_newznab_xml(data: bytes, indexer_url: str) -> list[IndexerResult]:
    """Parseia resposta XML do Newznab (fallback)."""
    root = ElementTree.fromstring(data)
    channel = root.find("channel")
    if channel is None:
        return []
    results = []
    for item in channel.findall("item"):
        title = item.findtext("title") or ""
        guid = item.findtext("guid") or ""
        link = item.findtext("link") or ""
        pub_date = item.findtext("pubDate") or ""
        enclosure = item.find("enclosure")
        if enclosure is not None and not link:
            link = enclosure.get("url", "")
        try:
            size_el = item.find(f"{{{_NEWZNAB_NS}}}attr[@name='size']")
            size = int(size_el.get("value", "0")) if size_el is not None else 0
        except (ValueError, TypeError):
            size = 0
        results.append(
            IndexerResult(
                title=title,
                guid=guid,
                nzb_url=link,
                size=size,
                pub_date=pub_date,
                indexer=indexer_url,
            )
        )
    return results


# ── NewznabClient ────────────────────────────────────────────────────────────


class NewznabClient:
    """Cliente Newznab com rate limiting e cache JSONL."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        rate_secs: float = _DEFAULT_RATE_SECS,
        cache_days: int = _DEFAULT_CACHE_DAYS,
        use_cache: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.rate_secs = rate_secs
        self.cache_days = cache_days
        self.use_cache = use_cache
        self._cache: Optional[dict[tuple[str, str], _CacheEntry]] = None

    def _get_cache(self) -> dict[tuple[str, str], _CacheEntry]:
        if self._cache is None:
            self._cache = _load_cache(self.cache_days)
        return self._cache

    def search(self, query: str, limit: int = 10) -> list[IndexerResult]:
        """Busca no indexador. Usa cache se disponível e não expirado."""
        norm_query = normalize_query(query)
        if not norm_query:
            return []

        if self.use_cache:
            cache = self._get_cache()
            key = _cache_key(norm_query, self.base_url)
            if key in cache:
                entry = cache[key]
                return [
                    IndexerResult(
                        title=r["title"],
                        guid=r["guid"],
                        nzb_url=r["nzb_url"],
                        size=int(r.get("size", 0)),
                        pub_date=r.get("pub_date", ""),
                        indexer=self.base_url,
                    )
                    for r in entry.results
                ]

        _rate_limit(self.base_url, self.rate_secs)

        params = urllib.parse.urlencode(
            {
                "t": "search",
                "q": norm_query,
                "apikey": self.api_key,
                "o": "json",
                "limit": str(limit),
            }
        )
        url = f"{self.base_url}?{params}"

        results: list[IndexerResult] = []
        try:
            raw = _http_get(url)
            # Tenta JSON primeiro, fallback para XML
            try:
                results = _parse_newznab_json(raw, self.base_url)
            except (json.JSONDecodeError, KeyError):
                results = _parse_newznab_xml(raw, self.base_url)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                # Rate limit do servidor — espera e re-tenta uma vez
                retry_after = float(exc.headers.get("Retry-After", "60"))
                time.sleep(min(retry_after, 120))
                raw = _http_get(url)
                try:
                    results = _parse_newznab_json(raw, self.base_url)
                except (json.JSONDecodeError, KeyError):
                    results = _parse_newznab_xml(raw, self.base_url)
            else:
                raise

        if self.use_cache:
            entry = _CacheEntry(
                query=norm_query,
                indexer_url=self.base_url,
                ts=time.time(),
                found=bool(results),
                results=[
                    {
                        "title": r.title,
                        "guid": r.guid,
                        "nzb_url": r.nzb_url,
                        "size": str(r.size),
                        "pub_date": r.pub_date,
                    }
                    for r in results
                ],
            )
            _save_entry(entry)
            cache = self._get_cache()
            cache[_cache_key(norm_query, self.base_url)] = entry

        return results

    def download_nzb(self, nzb_url: str, dest_path: str) -> str:
        """Baixa um NZB e salva em dest_path. Retorna o caminho gravado."""
        # Muitos indexadores precisam do apikey no download
        if "apikey=" not in nzb_url.lower() and self.api_key:
            sep = "&" if "?" in nzb_url else "?"
            nzb_url = f"{nzb_url}{sep}apikey={self.api_key}"

        _rate_limit(self.base_url, self.rate_secs)
        data = _http_get(nzb_url, timeout=30)
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return dest_path


# ── High-level helper ────────────────────────────────────────────────────────


def build_client_from_env(env_vars: dict[str, str]) -> Optional[NewznabClient]:
    """Cria NewznabClient a partir das variáveis de ambiente. Retorna None se não configurado."""
    base_url = env_vars.get("INDEXER_URL", "").strip()
    api_key = env_vars.get("INDEXER_APIKEY", "").strip()
    if not base_url or not api_key:
        return None
    try:
        rate_secs = float(env_vars.get("INDEXER_RATE_SECS", str(_DEFAULT_RATE_SECS)))
    except ValueError:
        rate_secs = _DEFAULT_RATE_SECS
    try:
        cache_days = int(env_vars.get("INDEXER_CACHE_DAYS", str(_DEFAULT_CACHE_DAYS)))
    except ValueError:
        cache_days = _DEFAULT_CACHE_DAYS
    return NewznabClient(base_url, api_key, rate_secs=rate_secs, cache_days=cache_days)


def check_and_prompt(
    name: str,
    env_vars: dict[str, str],
) -> bool:
    """
    Busca no indexador. Se encontrar, exibe os resultados, baixa o .nzb
    como backup local e pula o upload.

    Retorna True se o upload deve ser PULADO.
    Retorna False se deve continuar com o upload normalmente.
    """
    client = build_client_from_env(env_vars)
    if client is None:
        print("⚠️  Indexador não configurado (INDEXER_URL / INDEXER_APIKEY ausentes).")
        return False

    print(f"\n🔍 Buscando '{name}' no indexador...", flush=True)
    try:
        results = client.search(name, limit=5)
    except Exception as exc:
        print(f"⚠️  Erro ao buscar no indexador: {exc}")
        return False

    if not results:
        print("   Não encontrado no indexador. Prosseguindo com upload.")
        return False

    print(f"\n✅ Encontrado no indexador! {len(results)} resultado(s):")
    for i, r in enumerate(results[:5], 1):
        size_mb = r.size / (1024 * 1024) if r.size else 0
        size_str = f"{size_mb:.0f} MB" if size_mb else "?"
        print(f"  [{i}] {r.title[:80]}  ({size_str})")

    print("\nO que deseja fazer?")
    print("  [1] Baixar o .nzb como backup e pular o upload  (recomendado)")
    print("  [2] Escolher outro resultado da lista")
    print("  [3] Ignorar e continuar com upload mesmo assim")

    while True:
        choice = input("  Escolha [1/2/3]: ").strip()
        if choice in ("1", "2", "3"):
            break

    if choice == "3":
        return False

    if choice == "2":
        while True:
            idx_s = input(f"  Número do resultado [1-{len(results)}]: ").strip()
            try:
                idx = int(idx_s) - 1
                if 0 <= idx < len(results):
                    selected = results[idx]
                    break
            except ValueError:
                pass
    else:
        selected = results[0]

    safe_name = re.sub(r'[\\/*?"<>|]', "_", selected.title[:60])
    dest = os.path.join(INDEXER_NZB_DIR, f"{safe_name}.nzb")
    try:
        client.download_nzb(selected.nzb_url, dest)
        print(f"✅ .nzb salvo em: {dest}")
        print("   Upload pulado — conteúdo já disponível na Usenet.")
    except Exception as exc:
        print(f"❌ Erro ao baixar .nzb: {exc}")
        print("   Prosseguindo com upload por precaução.")
        return False

    return True
