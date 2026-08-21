import pytest

from calculator import safe_divide


def test_safe_divide_returns_numeric_result():
    assert safe_divide(9, 3) == 3


def test_safe_divide_rejects_zero_denominator():
    with pytest.raises(ValueError):
        safe_divide(9, 0)
