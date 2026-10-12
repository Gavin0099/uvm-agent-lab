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
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
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
