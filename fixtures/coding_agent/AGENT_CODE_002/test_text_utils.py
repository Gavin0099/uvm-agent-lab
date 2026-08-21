from text_utils import normalize_words


def test_normalize_words_collapses_whitespace_and_case():
    assert normalize_words("  Local   AI  ") == "local ai"


def test_normalize_words_handles_empty_input():
    assert normalize_words("   ") == ""
