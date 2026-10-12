"""Literal-source fixtures independently define the permissible quote changes."""
import pytest

from gv100h.spec_qa.source_binding.quote_layout import match_quote, QUOTE_MATCHER_VERSION


@pytest.mark.parametrize("source,quote,kind", [
    ("prefix over-\ncurrent condition suffix", "over-current condition", "hyphen_line_join"),
    ("over- \r\n  current and self-\npowered", "over-current and self-powered", "hyphen_line_join"),
    ("over-current\n  condition", "over-current condition", "exact_whitespace"),
    ("2 pF maximum unmated per contact", "2 pF maximum unmated per contact", "exact_whitespace"),
    ("The mechanism can be used.", "can be used.", "exact_whitespace"),
    ("literal ... in the source", "literal ... in the source", "exact_whitespace"),
])
def test_exact_original_contiguous_span_is_returned(source, quote, kind):
    result = match_quote(quote, source)
    assert result["match_kind"] == kind
    assert source[result["source_start"]:result["source_end"]] == result["original_quote"]
    assert result["matcher_version"] == QUOTE_MATCHER_VERSION


@pytest.mark.parametrize("source,quote", [
    ("alpha intervening beta", "alpha ... beta"),
    ("alpha intervening beta", "alpha beta"),
    ("The mechanism can be used.", "The mechanism must be used."),
    ("The mechanism may be used.", "The mechanism always is used."),
    ("2 pF maximum unmated per contact", "3 pF maximum unmated per contact"),
    ("over-\ncurrent condition", "overcurrent condition"),
    ("over-\ncurrent condition", "under-current condition"),
    ("over-\ncurrent condition", "over–current condition"),
    ("2-\n8 pF maximum", "2-8 pF maximum"),
    ("over-\n\ncurrent condition", "over-current condition"),
    ("over- current condition", "over-current condition"),
    ("word", ""), ("word", " "), ("word", None),
])
def test_rewrite_ellipsis_splicing_or_unsupported_join_is_rejected(source, quote):
    assert match_quote(quote, source) is None


def test_faithful_quote_does_not_check_claim_modality():
    source = "The mechanism can be used to observe an event."
    result = match_quote(source, source)
    assert result["original_quote"] == source
    assert "can" in result["original_quote"]
    # No claim input: separate semantic review must reject an always/must claim.


@pytest.mark.parametrize("source", ["alpha\n\nbeta", "alpha\r\n\r\nbeta", "alpha\n \t\nbeta", "alpha\u2029beta"])
def test_whitespace_matching_cannot_collapse_source_paragraph_boundaries(source):
    assert match_quote("alpha beta", source) is None


def test_verbatim_paragraph_separator_is_preserved_without_joining():
    source = "prefix alpha\n\nbeta suffix"
    result = match_quote("alpha\n\nbeta", source)
    assert result["original_quote"] == "alpha\n\nbeta"
    assert source[result["source_start"]:result["source_end"]] == result["original_quote"]


def test_single_line_wrap_remains_supported():
    assert match_quote("alpha beta", "alpha\n beta")["original_quote"] == "alpha\n beta"


def test_model_bare_cr_paragraph_is_not_erased_by_tokenization():
    assert match_quote("alpha\r\rbeta", "alpha beta") is None


def test_verbatim_source_bare_cr_separator_is_preserved():
    source = "alpha\r\rbeta"
    result = match_quote(source, source)
    assert result["original_quote"] == source
    assert source[result["source_start"]:result["source_end"]] == source


@pytest.mark.parametrize("gap", ["\x1c", "\x1d", "\x1e"])
def test_other_record_separators_are_not_horizontal_layout_whitespace(gap):
    assert match_quote("alpha" + gap + "beta", "alpha beta") is None
    assert match_quote("alpha beta", "alpha" + gap + "beta") is None


def test_unicode_horizontal_space_can_still_be_normalized():
    assert match_quote("alpha beta", "alpha\u00a0beta")["original_quote"] == "alpha\u00a0beta"
