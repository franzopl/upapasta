import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from upapasta.tmdb import _get_details, parse_title_and_year, search_media, validate_confident_match


def test_validate_confident_match():
    # Sucesso: Título exato + Ano exato
    item = {"title": "The Matrix", "release_date": "1999-03-31"}
    assert validate_confident_match("Matrix", "1999", item) is True

    # Falha: Ano divergente
    item = {"title": "The Matrix", "release_date": "2021-12-22"}
    assert validate_confident_match("The Matrix", "1999", item) is False

    # Sucesso: Sem ano no arquivo, mas título é bom
    item = {"title": "Fight Club", "release_date": "1999-10-15"}
    assert validate_confident_match("Fight Club", None, item) is True

    # Falha: Títulos totalmente diferentes
    item = {"title": "Toy Story", "release_date": "1995-11-22"}
    assert validate_confident_match("The Matrix", None, item) is False


@patch("urllib.request.urlopen")
def test_search_media_strict_rejects_bad_year(mock_urlopen):
    # Mock retorna um filme com ano errado (ex: remake de 2021 em vez do original de 1999)
    response = MagicMock()
    response.read.return_value = json.dumps(
        {
            "results": [
                {"id": 456, "title": "The Matrix Resurrections", "release_date": "2021-12-22"}
            ]
        }
    ).encode("utf-8")
    response.__enter__.return_value = response
    mock_urlopen.return_value = response

    # Busca por Matrix 1999, mas a API retornou 2021 como primeiro resultado
    item, suggestions = search_media("fake_key", "Matrix", "1999", strict=True)
    assert item is None
    assert len(suggestions) == 1
    assert suggestions[0]["id"] == 456


def test_parse_title_and_year():
    assert parse_title_and_year("The.Matrix.1999.1080p.mkv") == ("The Matrix", "1999")
    assert parse_title_and_year("Stranger.Things.S01E01.720p.hdtv.x264") == (
        "Stranger Things S01E01",
        None,
    )
    assert parse_title_and_year("Fight.Club.1999.Bluray.1080p.DTS-HD.x264.mkv") == (
        "Fight Club",
        "1999",
    )
    assert parse_title_and_year("Filme.Sem.Ano.1080p.mkv") == ("Filme Sem Ano", None)
    assert parse_title_and_year("O.Auto.da.Compadecida.(2000).mp4") == (
        "O Auto da Compadecida",
        "2000",
    )
    assert parse_title_and_year("Test.2024.7z") == ("Test", "2024")


@patch("urllib.request.urlopen")
def test_search_media_movie_success(mock_urlopen):
    # Mock search results
    search_response = MagicMock()
    search_response.read.return_value = json.dumps(
        {"results": [{"id": 123, "title": "Matrix", "release_date": "1999-03-31"}]}
    ).encode("utf-8")
    search_response.__enter__.return_value = search_response

    # Mock details/external_ids results
    details_response = MagicMock()
    details_response.read.return_value = json.dumps(
        {
            "external_ids": {"imdb_id": "tt0133093"},
            "genres": [{"name": "Action"}],
            "overview": "Sinopse...",
        }
    ).encode("utf-8")
    details_response.__enter__.return_value = details_response

    mock_urlopen.side_effect = [search_response, details_response]

    item, _ = search_media("fake_key", "Matrix", "1999")
    assert item is not None
    assert item["title"] == "Matrix"
    assert item["imdb_id"] == "tt0133093"
    assert "Action" in item["genres"]


@patch("urllib.request.urlopen")
def test_search_media_no_results(mock_urlopen):
    response = MagicMock()
    response.read.return_value = json.dumps({"results": []}).encode("utf-8")
    response.__enter__.return_value = response
    mock_urlopen.return_value = response

    item, suggestions = search_media("fake_key", "NonExistentMovie")
    assert item is None
    assert suggestions == []


@patch("urllib.request.urlopen")
def test_search_media_api_error(mock_urlopen):
    mock_urlopen.side_effect = Exception("API Error")
    item, suggestions = search_media("fake_key", "Matrix")
    assert item is None
    assert suggestions == []


@patch("urllib.request.urlopen")
def test_get_details_failure(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("Fail")
    result = _get_details("fake_key", 123, "movie", "pt-BR")
    assert result is None


def test_tmdb_search_main_logic(monkeypatch, capsys):
    """Testa a lógica do utilitário --tmdb-search em main.py."""
    import sys

    from upapasta.main import main

    # Mock de argumentos
    class FakeArgs:
        tmdb_search = "Matrix"
        env_file = None
        verbose = False
        log_file = None
        insecure = False

    monkeypatch.setattr(sys, "argv", ["upapasta", "--tmdb-search", "Matrix"])

    # Mock do .env (precisa ser no namespace de main, não de config)
    monkeypatch.setattr("upapasta.main.load_env_file", lambda f: {"TMDB_API_KEY": "fake_key"})
    monkeypatch.setattr("upapasta.main.resolve_env_file", lambda f=None: ".env")

    # Mock do search_media
    mock_item = {"id": 603, "title": "The Matrix", "release_date": "1999-03-31"}
    mock_suggestions = [mock_item]

    with patch("upapasta.tmdb.search_media", return_value=(mock_item, mock_suggestions)):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0

    captured = capsys.readouterr()
    assert "Resultados encontrados" in captured.out
    assert "The Matrix (1999) ID: 603" in captured.out
