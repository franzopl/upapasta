"""
test_main_dispatch.py

Cobertura de dispatch points e modos em main.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from upapasta.main import main


class TestMainConfigDispatch:
    """Testes do dispatch --config."""

    def test_config_flag_calls_check_or_prompt(self, capsys):
        """--config deve chamar check_or_prompt_credentials e sair com code 0."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = True
            mock_args.profile = None
            mock_args.env_file = None
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.check_or_prompt_credentials") as mock_check:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    mock_check.assert_called_once()

    def test_config_flag_with_profile(self, capsys):
        """--config com --profile deve usar profile correto."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = True
            mock_args.profile = "myprofile"
            mock_args.env_file = None
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/config/myprofile.env"

                with patch("upapasta.main.check_or_prompt_credentials"):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    mock_resolve.assert_called_with("myprofile")


class TestMainStatsDispatch:
    """Testes do dispatch --stats."""

    def test_stats_flag_calls_print_stats(self, capsys):
        """--stats deve chamar print_stats e sair com code 0."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = True
            mock_args.profile = None
            mock_args.env_file = None
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.print_stats") as mock_stats:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    mock_stats.assert_called_once()


class TestMainTestConnectionDispatch:
    """Testes do dispatch --test-connection."""

    def test_test_connection_incomplete_credentials(self, capsys):
        """--test-connection sem credenciais completas deve sair com code 1."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = False
            mock_args.test_connection = True
            mock_args.profile = None
            mock_args.env_file = None
            mock_args.insecure = False
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}  # Sem credenciais
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

    def test_test_connection_success(self, capsys):
        """--test-connection com credenciais válidas retorna code 0."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = False
            mock_args.test_connection = True
            mock_args.profile = None
            mock_args.env_file = None
            mock_args.insecure = False
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {
                        "NNTP_HOST": "news.example.com",
                        "NNTP_PORT": "119",
                        "NNTP_USER": "user",
                        "NNTP_PASS": "pass",
                        "NNTP_SSL": "true",
                    }

                    with patch("upapasta.main.check_nntp_connection") as mock_test:
                        mock_test.return_value = (True, "✅ Connected")
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 0

    def test_test_connection_failure(self, capsys):
        """--test-connection com falha retorna code 1."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = False
            mock_args.test_connection = True
            mock_args.profile = None
            mock_args.env_file = None
            mock_args.insecure = False
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {
                        "NNTP_HOST": "news.example.com",
                        "NNTP_PORT": "119",
                        "NNTP_USER": "user",
                        "NNTP_PASS": "pass",
                        "NNTP_SSL": "false",
                    }

                    with patch("upapasta.main.check_nntp_connection") as mock_test:
                        mock_test.return_value = (False, "❌ Connection failed")
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 1


class TestMainTmdbSearchDispatch:
    """Testes do dispatch --tmdb-search."""

    def test_tmdb_search_no_api_key(self, capsys):
        """--tmdb-search sem API key deve sair com code 1."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = False
            mock_args.test_connection = False
            mock_args.tmdb_search = "Dune 2024"
            mock_args.profile = None
            mock_args.env_file = None
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}  # Sem TMDB_API_KEY
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

    def test_tmdb_search_with_results(self, capsys):
        """--tmdb-search com resultados deve exibir e sair com code 0."""
        from argparse import Namespace

        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = Namespace(
                config=False,
                stats=False,
                test_connection=False,
                tmdb_search="Dune 2024",
                profile=None,
                env_file=None,
            )
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {"TMDB_API_KEY": "fake_key"}

                    with patch("upapasta.tmdb.parse_title_and_year") as mock_parse_title:
                        mock_parse_title.return_value = ("Dune", 2024)

                        with patch("upapasta.tmdb.search_media") as mock_search:
                            mock_search.side_effect = [
                                (
                                    False,
                                    [
                                        {
                                            "id": 438631,
                                            "title": "Dune: Part Two",
                                            "release_date": "2024-02-28",
                                        }
                                    ],
                                ),
                                (False, []),
                            ]

                            with pytest.raises(SystemExit) as exc_info:
                                main()
                            assert exc_info.value.code == 0
                            captured = capsys.readouterr()
                            assert "Resultados encontrados" in captured.out


class TestMainNoInputsDispatch:
    """Testes quando nenhum input é fornecido."""

    def test_no_inputs_prints_usage(self, capsys):
        """Sem inputs deve exibir uso amigável e sair com code 0."""
        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.config = False
            mock_args.stats = False
            mock_args.test_connection = False
            mock_args.tmdb_search = None
            mock_args.inputs = None
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0


class TestMainMultiInput:
    """Testes do modo multi-input (múltiplos paths posicionais)."""

    def test_multi_input_sequential(self, tmp_path, capsys):
        """Múltiplos inputs em modo sequencial."""
        # Cria 2 arquivos de teste
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_text("test1")
        f2.write_text("test2")

        from argparse import Namespace

        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = Namespace(
                config=False,
                stats=False,
                test_connection=False,
                tmdb_search=None,
                inputs=[str(f1), str(f2)],
                input=str(f1),
                jobs=1,
                verbose=False,
                log_file=None,
                profile=None,
                env_file=None,
            )
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}

                    with patch("upapasta.main._validate_flags") as mock_validate:
                        mock_validate.return_value = True

                        with patch("upapasta.main.check_dependencies") as mock_deps:
                            mock_deps.return_value = True

                            with patch("upapasta.main._run_single_input") as mock_run:
                                mock_run.return_value = 0

                                with pytest.raises(SystemExit) as exc_info:
                                    main()
                                assert exc_info.value.code == 0
                                # Deve ter chamado _run_single_input 2x
                                assert mock_run.call_count == 2


class TestMainEachMode:
    """Testes do modo --each."""

    def test_each_mode_determines_items_to_process(self, tmp_path, capsys):
        """--each deve detectar apenas arquivos válidos, ignorando skip_extensions."""
        # Cria arquivos de teste
        (tmp_path / "video.mkv").write_text("video")
        (tmp_path / "video.nzb").write_text("nzb")  # Deve ser ignorado
        (tmp_path / "file.par2").write_text("par2")  # Deve ser ignorado
        (tmp_path / "file.part1").write_text("part")  # Deve ser ignorado
        (tmp_path / "archive.vol01").write_text("vol")  # Deve ser ignorado

        from argparse import Namespace

        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = Namespace(
                config=False,
                stats=False,
                test_connection=False,
                tmdb_search=None,
                inputs=[str(tmp_path)],
                input=str(tmp_path),
                each=True,
                watch=False,
                verbose=False,
                log_file=None,
                profile=None,
                env_file=None,
            )
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}

                    with patch("upapasta.main._validate_flags") as mock_validate:
                        mock_validate.return_value = True

                        with patch("upapasta.main.check_dependencies") as mock_deps:
                            mock_deps.return_value = True

                            # Mockar setup_session_log para não criar logs reais
                            with patch("upapasta.main.setup_session_log") as mock_setup_log:
                                mock_setup_log.return_value = ("/tmp/test.log", None)

                                # Mockar UpaPastaOrchestrator para não tentar processar
                                with patch("upapasta.main.UpaPastaOrchestrator.from_args"):
                                    with patch("upapasta.main.UpaPastaSession"):
                                        with pytest.raises(SystemExit):
                                            main()
                                        # Deve ter tentado processar 1 arquivo válido (video.mkv)
                                        assert mock_setup_log.call_count == 1
                                        call_args = mock_setup_log.call_args
                                        assert "video.mkv" in str(call_args)

    def test_each_mode_empty_folder(self, tmp_path, capsys):
        """--each em pasta vazia deve sair com code 1."""
        from argparse import Namespace

        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = Namespace(
                config=False,
                stats=False,
                test_connection=False,
                tmdb_search=None,
                inputs=[str(tmp_path)],
                input=str(tmp_path),
                each=True,
                watch=False,
                verbose=False,
                log_file=None,
                profile=None,
                env_file=None,
            )
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}

                    with patch("upapasta.main._validate_flags") as mock_validate:
                        mock_validate.return_value = True

                        with patch("upapasta.main.check_dependencies") as mock_deps:
                            mock_deps.return_value = True

                            with pytest.raises(SystemExit) as exc_info:
                                main()
                            assert exc_info.value.code == 1


class TestMainWatchMode:
    """Testes do modo --watch."""

    def test_watch_mode_calls_watch_loop(self, tmp_path, capsys):
        """--watch deve chamar _watch_loop."""
        from argparse import Namespace

        with patch("upapasta.main.parse_args") as mock_parse:
            mock_args = Namespace(
                config=False,
                stats=False,
                test_connection=False,
                tmdb_search=None,
                inputs=[str(tmp_path)],
                input=str(tmp_path),
                each=False,
                watch=True,
                watch_interval=5,
                watch_stable=2,
                verbose=False,
                log_file=None,
                profile=None,
                env_file=None,
            )
            mock_parse.return_value = mock_args

            with patch("upapasta.main.resolve_env_file") as mock_resolve:
                mock_resolve.return_value = "/tmp/test.env"

                with patch("upapasta.main.load_env_file") as mock_load:
                    mock_load.return_value = {}

                    with patch("upapasta.main._validate_flags") as mock_validate:
                        mock_validate.return_value = True

                        with patch("upapasta.main.check_dependencies") as mock_deps:
                            mock_deps.return_value = True

                            with patch("upapasta.main._watch_loop") as mock_watch:
                                with pytest.raises(SystemExit) as exc_info:
                                    main()
                                assert exc_info.value.code == 0
                                mock_watch.assert_called_once()
