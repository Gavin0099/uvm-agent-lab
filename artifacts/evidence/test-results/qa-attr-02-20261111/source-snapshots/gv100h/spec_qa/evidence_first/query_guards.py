"""Pure query applicability checks; never rewrite a query or source text."""
import re
import unicodedata


def normalized_query(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return ''.join('-' if unicodedata.category(ch) == 'Pd' or ch in '\u00ad\u2212'
                   else ch for ch in text)


_NUMBER = r'[0-9]+(?:\s*\.\s*[0-9]+)*(?:[a-z])?'
# Capture the whole supplied value, including unsupported suffixes. Never
# backtrack a malformed value into a supported numeric prefix.
_VALUE = r'(?>[0-9]+(?:\s*\.\s*[0-9]+)*[^\s()\[\]{},;/，、?？!！:：&\u3400-\u9fff]*)'
_MARKER = r'(?:document\s+revision|(?:文件|規格)修訂版|修訂版|rev(?:ision)?\.?)'
_REVISION = re.compile(r'(?<![a-z0-9_])(' + _MARKER + r')\s*[:\-]?\s*(' + _VALUE + r')')
_DOCUMENT_END = re.compile(
    r'(?<![a-z0-9_])(?:usb[\s-]*(?:v(?:ersion)?[\s-]*)?[0-9]+(?:\s*\.\s*[0-9]+)*'
    r'|superspeed\s+hub\s+lvs)(?:\s+(?:test\s+)?(?:specification|spec|document)|\s*規格)?(?:\s*的)?'
    r'[\s(\[,:-]*$')
_NEXT_REVISION = re.compile(r'\s*(?:/|,|&|\band\b|\bor\b|\bto\b|\bthrough\b|以及|及|和|與|、|到|至|[-–])\s*'
                            r'(?:' + _MARKER + r'\s*[:\-]?\s*)?(' + _VALUE + r')')


def revision_key(metadata):
    """Only a complete metadata revision is usable; no numbers from titles."""
    text = normalized_query(metadata).strip()
    text = re.sub(r'^' + _MARKER + r'\s*', '', text).strip()
    return re.sub(r'\s+', '', text) if re.fullmatch(_NUMBER, text) else None


def requested_revisions(question):
    """Recognize explicit document context, not device/field revision values.

    A bare leading Rev uses the explicitly selected source scope. Else the
    marker must follow a specification name or say document/文件/規格 revision.
    Lists/ranges require every requested revision, so cannot silently fall
    back to the one available member.
    """
    text = normalized_query(question)
    revisions = set()
    def value_key(value):
        value = re.sub(r'\s+', '', value)
        # A single sentence-ending full stop is punctuation only when the
        # preceding complete value is valid. Dotted/Unicode suffixes stay
        # opaque and unsupported, rather than becoming a numeric prefix.
        if value.endswith('.') and revision_key(value[:-1]) is not None:
            return value[:-1]
        return value
    for match in _REVISION.finditer(text):
        prefix = text[:match.start()]
        explicit = match.group(1).startswith(('document', '文件', '規格'))
        if not (explicit or not prefix.strip() or _DOCUMENT_END.search(prefix)):
            continue
        revisions.add(value_key(match.group(2)))
        end = match.end()
        while following := _NEXT_REVISION.match(text, end):
            revisions.add(value_key(following.group(1)))
            end = following.end()
    return revisions


_IDENTIFIER = r'(?:[A-Za-z_]|[^\W\d\u3400-\u9fff])(?:[A-Za-z0-9_\u0300-\u036f]|[^\W\u3400-\u9fff])*'
_TOKEN = re.compile(r'(?<![A-Za-z0-9_])' + _IDENTIFIER + r'(?![A-Za-z0-9_])')


def identifier_tokens(text):
    """Case-sensitive word tokens; keep Unicode suffixes, separate CJK prose.

    A non-ASCII suffix must never turn into the prefix of a known field.
    Source text is not normalized.
    """
    return set(_TOKEN.findall(text))


def requested_identifiers(question):
    """Code-shaped names or explicit identifier literals only.

    Ordinary English words and unquoted acronyms remain general search terms.
    NFKC applies to query spelling alone, never to the owned source text.
    """
    text = unicodedata.normalize('NFKC', question)
    result = set()
    # Read a quoted single-token literal as a whole and mask it before the
    # implicit scan. A known ASCII prefix inside a different literal is never
    # evidence that the requested literal exists. Multi-word quotes are prose.
    masked = list(text)
    label = r'(?i)(?<![A-Za-z0-9_])(?:identifier|識別字)\s*[:：]?\s*'
    for match in re.finditer(r'[`\"\'“‘「]([^`\"\'”’」\n]+)[`\"\'”’」]', text):
        literal = match.group(1).strip()
        prefix_label = re.search(label + '$', text[:match.start()])
        if (literal and not any(c.isspace() for c in literal)
                and (re.fullmatch(_IDENTIFIER, literal)
                     or re.search(r'[a-z][A-Z]|_', literal)
                     or prefix_label)):
            result.add(literal)
        start = prefix_label.start() if prefix_label else match.start()
        masked[start:match.end()] = ' ' * (match.end() - start)
    text = ''.join(masked)
    result.update(word for word in identifier_tokens(text)
                  if re.search(r'[a-z][A-Z]', word) or ('_' in word and re.search(r'[A-Za-z]', word)))
    result.update(re.findall(label + '(' + _IDENTIFIER + r')(?![A-Za-z0-9_])', text))
    return result
