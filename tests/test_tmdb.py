import json
import urllib.error
from unittest.mock import MagicMock, patch

from upapasta.tmdb import _get_details, parse_title_and_year, search_media


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

    result = search_media("fake_key", "Matrix", "1999")
    assert result is not None
    assert result["title"] == "Matrix"
    assert result["imdb_id"] == "tt0133093"
    assert "Action" in result["genres"]


@patch("urllib.request.urlopen")
def test_search_media_no_results(mock_urlopen):
    response = MagicMock()
    response.read.return_value = json.dumps({"results": []}).encode("utf-8")
    response.__enter__.return_value = response
    mock_urlopen.return_value = response

    result = search_media("fake_key", "NonExistentMovie")
    assert result is None


@patch("urllib.request.urlopen")
def test_search_media_api_error(mock_urlopen):
    mock_urlopen.side_effect = Exception("API Error")
    result = search_media("fake_key", "Matrix")
    assert result is None


@patch("urllib.request.urlopen")
def test_get_details_failure(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("Fail")
    result = _get_details("fake_key", 123, "movie", "pt-BR")
    assert result is None
