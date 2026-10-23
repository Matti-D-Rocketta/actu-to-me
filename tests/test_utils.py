from datetime import timedelta

import pytest

from src.utils import clean_url, parse_since


@pytest.mark.parametrize("raw,expected", [
    ("24h", timedelta(hours=24)), ("7d", timedelta(days=7)), (" 48H ", timedelta(hours=48)),
])
def test_parse_since(raw, expected):
    assert parse_since(raw) == expected


def test_parse_since_invalid():
    with pytest.raises(ValueError):
        parse_since("3w")


def test_clean_url_strips_tracking():
    assert clean_url("https://ex.com/a/b?utm_source=x#top") == "https://ex.com/a/b"
