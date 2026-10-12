"""Continuous original spans under the existing bounded PDF layout rule.

A matching quote does not establish claim support or preserve modality.
Returned offsets address the untouched original source, never normalized text.
"""
import re

QUOTE_MATCHER_VERSION = "usb-quote-layout.v2"

def match_quote(quote, source):
    """Match whitespace or a single PDF line wrap; retain exact source offsets.

    Only remove one physical newline/indentation after an ASCII-letter hyphen
    and before another ASCII letter. Keep the hyphen, letters, numbers and
    punctuation. No fuzzy matching, digit-range joining or paragraph joining.
    """
    if not isinstance(quote, str) or not quote.strip():
        return None
    # A literal continuous excerpt can retain paragraph separators as-is.
    literal = source.find(quote)
    if literal >= 0:
        return {"original_quote": quote, "source_start": literal,
                "source_end": literal + len(quote), "match_kind": "exact_whitespace",
                "matcher_version": QUOTE_MATCHER_VERSION}
    # Unicode space separators (Zs) and TAB; vertical/record controls are not
    # horizontal whitespace even when Python str.split treats them as space.
    horizontal = r"[\t \u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]"
    # Layout normalization supports horizontal whitespace or one physical line
    # wrap only. Paragraph/page separators must never be silently collapsed.
    separator = r"(?:" + horizontal + r"+|" + horizontal + r"*\r?\n" + horizontal + r"*)"
    if any(re.fullmatch(separator, gap) is None for gap in re.findall(r"\s+", quote)):
        return None
    pattern = separator.join(re.escape(word) for word in quote.split())
    match = re.search(pattern, source)
    if match:
        start, end, kind = match.start(), match.end(), "exact_whitespace"
    else:
        gaps = list(re.finditer(r"(?<=[A-Za-z]-)[ \t]*\r?\n[ \t]*(?=[A-Za-z])", source))
        if not gaps:
            return None
        positions, cursor = [], 0
        for gap in gaps:
            positions.extend(range(cursor, gap.start()))
            cursor = gap.end()
        positions.extend(range(cursor, len(source)))
        flattened = "".join(source[i] for i in positions)
        match = re.search(pattern, flattened)
        if not match:
            return None
        start, end, kind = positions[match.start()], positions[match.end() - 1] + 1, "hyphen_line_join"
    return {"original_quote": source[start:end], "source_start": start,
            "source_end": end, "match_kind": kind, "matcher_version": QUOTE_MATCHER_VERSION}
