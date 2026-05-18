from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_find_pesto():
    """By default, ensure pesto is NOT found in tests unless specifically enabled."""
    with patch("upapasta.upfolder.find_pesto", return_value=None):
        yield
