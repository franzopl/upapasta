from unittest.mock import patch

from upapasta.nfo import generate_nfo_from_template


def test_generate_nfo_from_template_basic(tmp_path):
    template = tmp_path / "template.txt"
    template.write_text("Title: {{title}}\nYear: {{year}}\nSize: {{size}}")

    input_file = tmp_path / "Film.2024.mkv"
    input_file.write_text("dummy")

    nfo_out = tmp_path / "test.nfo"

    # Mocking mediainfo to avoid external dependency
    with patch("upapasta.nfo.find_mediainfo", return_value=None):
        result = generate_nfo_from_template(str(template), str(input_file), str(nfo_out))

    assert result is True
    content = nfo_out.read_text()
    assert "Title: Film" in content
    assert "Year: 2024" in content
    assert "Size: 5 B" in content


def test_generate_nfo_from_template_with_tmdb(tmp_path):
    template = tmp_path / "template.txt"
    template.write_text("{{title}} ({{year}})\nIMDB: {{imdb_url}}\nSynopsis: {{synopsis}}")

    input_file = tmp_path / "film.mkv"
    input_file.write_text("x")

    tmdb_data = {
        "title": "The Movie",
        "release_date": "2020-01-01",
        "imdb_id": "tt1234567",
        "overview": "This is a movie.",
    }

    nfo_out = tmp_path / "test.nfo"

    result = generate_nfo_from_template(
        str(template), str(input_file), str(nfo_out), tmdb_metadata=tmdb_data
    )

    assert result is True
    content = nfo_out.read_text()
    assert "The Movie (2020)" in content
    assert "IMDB: https://www.imdb.com/title/tt1234567" in content
    assert "Synopsis: This is a movie." in content


def test_generate_nfo_from_template_missing_file(tmp_path):
    result = generate_nfo_from_template("non_existent.txt", "input", "out.nfo")
    assert result is False


def test_generate_nfo_from_template_folder(tmp_path):
    template = tmp_path / "template.txt"
    template.write_text("Folder: {{title}}\nFiles:\n{{files}}")

    folder = tmp_path / "MyFolder"
    folder.mkdir()
    (folder / "file1.txt").write_text("one")
    (folder / "file2.txt").write_text("two")

    nfo_out = tmp_path / "test.nfo"

    # Mocking tree generation to simplify
    with patch("upapasta.nfo._generate_tree", return_value=(["file1.txt", "file2.txt"], 0, 2)):
        result = generate_nfo_from_template(str(template), str(folder), str(nfo_out))

    assert result is True
    content = nfo_out.read_text()
    assert "Folder: MyFolder" in content
    assert "file1.txt" in content
    assert "file2.txt" in content
