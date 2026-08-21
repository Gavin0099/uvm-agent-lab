import pytest

from settings import retry_limit


def test_retry_limit_defaults_to_three():
    assert retry_limit() == 3


def test_retry_limit_preserves_valid_override():
    assert retry_limit(7) == 7


def test_retry_limit_rejects_non_positive_override():
    with pytest.raises(ValueError):
        retry_limit(0)
