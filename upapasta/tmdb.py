"""
tmdb.py

Cliente minimalista para a API do The Movie Database (TMDb).
Usa apenas bibliotecas padrão do Python.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Optional, cast


def parse_title_and_year(name: str) -> tuple[str, Optional[str]]:
    """Extrai título limpo e ano de uma string de nome de arquivo/pasta."""
    # Remove extensões comuns
    name = re.sub(r"\.(mkv|mp4|avi|mov|rar|7z)$", "", name, flags=re.IGNORECASE)

    # Tenta encontrar ano (4 dígitos entre 1900 e 2099) cercado por separadores
    year_match = re.search(r"[\s._\[(](19\d{2}|20[0-2]\d)([\s._\])]|$)", name)
    year = year_match.group(1) if year_match else None

    # Limpa o título: pega tudo antes do ano ou de tags comuns (1080p, x264, etc.)
    clean_name = name
    if year_match:
        clean_name = name[: year_match.start()]

    # Corta em tags comuns (independente de ter ano ou não)
    tags = [
        "1080p",
        "720p",
        "2160p",
        "4k",
        "bluray",
        "hdtv",
        "web-dl",
        "webrip",
        "x264",
        "x265",
        "hevc",
    ]
    for tag in tags:
        # Busca a tag precedida por um separador
        tag_match = re.search(rf"[\s._-]{tag}([\s._-]|$)", clean_name, re.IGNORECASE)
        if tag_match:
            clean_name = clean_name[: tag_match.start()]

    # Substitui separadores por espaços
    clean_name = re.sub(r"[\s._-]+", " ", clean_name).strip()

    return clean_name, year


def _normalize_for_search(text: str) -> str:
    """Normaliza string para comparação: minúsculas, sem acentos e sem símbolos."""
    text = text.lower()
    # Remove acentos simplificado
    table = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüç",
        "aaaaaeeeeiiiiooooouuuuc",
    )
    text = text.translate(table)
    # Mantém apenas letras e números
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Colapsa múltiplos espaços
    return " ".join(text.split())


def validate_confident_match(
    query_title: str,
    query_year: Optional[str],
    result: dict[str, Any],
    media_type: str = "movie",
) -> bool:
    """
    Verifica se um resultado do TMDb é confiável com base no título e ano.
    Retorna True se houver alta confiança.
    """
    res_title = result.get("title") or result.get("name", "")
    res_date = result.get("release_date") or result.get("first_air_date") or ""
    res_year = res_date[:4] if len(res_date) >= 4 else None

    # 1. Se informamos ano no arquivo, ele DEVE bater com o resultado (filtro de remakes/homônimos)
    if query_year and res_year and query_year != res_year:
        return False

    # 2. Comparação de títulos normalizados
    n_query = _normalize_for_search(query_title)
    n_res = _normalize_for_search(res_title)

    # Se um título contém o outro integralmente (ex: "Matrix" in "The Matrix"), é confiável.
    if n_query in n_res or n_res in n_query:
        return True

    # 3. Verificação por palavras (fuzzy simplificado)
    # Se pelo menos 80% das palavras do título buscado estão no resultado
    words_query = set(n_query.split())
    words_res = set(n_res.split())
    if not words_query:
        return False

    matches = words_query.intersection(words_res)
    confidence = len(matches) / len(words_query)

    return confidence >= 0.8


def search_media(
    api_key: str,
    title: str,
    year: Optional[str] = None,
    media_type: str = "movie",
    language: str = "pt-BR",
    strict: bool = True,
) -> Optional[dict[str, Any]]:
    """Busca um filme ou série no TMDb e retorna o resultado mais relevante."""
    base_url = "https://api.themoviedb.org/3/search/"
    endpoint = "movie" if media_type == "movie" else "tv"

    params = {
        "api_key": api_key,
        "query": title,
        "language": language,
    }
    if year:
        key = "primary_release_year" if media_type == "movie" else "first_air_date_year"
        params[key] = year

    url = f"{base_url}{endpoint}?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                return None
            results = data.get("results", [])
            if not results:
                # Tenta sem o ano se falhar com o ano (talvez o ano no arquivo esteja errado)
                # Mas se strict=True, o validate_confident_match cuidará de barrar depois.
                if year:
                    return search_media(api_key, title, None, media_type, language, strict=strict)
                return None

            # Pega o primeiro resultado (mais relevante)
            item = results[0]

            # Validação de Confiança (Heurística)
            if strict:
                if not validate_confident_match(title, year, item, media_type):
                    return None

            tmdb_id = item.get("id")

            # Busca detalhes extras (como external IDs para IMDB)
            details = _get_details(api_key, tmdb_id, media_type, language)
            if details:
                item.update(details)

            return cast("dict[str, Any]", item)
    except Exception:
        return None


def _get_details(
    api_key: str, tmdb_id: int, media_type: str, language: str
) -> Optional[dict[str, Any]]:
    """Busca detalhes e IDs externos de um item."""
    base_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    params = {"api_key": api_key, "language": language, "append_to_response": "external_ids"}

    url = f"{base_url}?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                return None
            ext_ids = data.get("external_ids", {})
            return {
                "imdb_id": ext_ids.get("imdb_id"),
                "genres": [g.get("name") for g in data.get("genres", [])],
                "tagline": data.get("tagline"),
                "runtime": data.get("runtime"),  # apenas movie
                "status": data.get("status"),
            }
    except Exception:
        return None
