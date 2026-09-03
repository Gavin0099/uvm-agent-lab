"""Deterministic selection of answer-supporting evidence candidates.

The local model does not emit citation IDs, so this module deliberately does
not claim to observe the model's internal evidence use. It produces an
explainable lexical set-cover selection from retrieved candidates for UI
citation projection only. Semantic entailment remains outside this
development path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Sequence, Tuple

from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    GovernedChunkRetrievalHit,
)

EVIDENCE_SELECTION_METHOD = "deterministic_lexical_v1"

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[_./-][A-Za-z0-9]+)*")
_MEASUREMENT_NUMBER_PATTERN = (
    r"[+-]?(?:(?:\d+(?:\.\d+)?)|(?:\.\d+))(?:[eE][+-]?\d+)?"
)
_MEASUREMENT_UNIT_PATTERN = (
    r"(?:ohms?|Ω|ω|volts?|bits?|ps|ns|us|ms|pf|mv|uv|ma|ua|mhz|khz|ghz|v|a)"
)
_NUMBER_UNIT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    + _MEASUREMENT_NUMBER_PATTERN
    + r"\s*"
    + _MEASUREMENT_UNIT_PATTERN
    + r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_SECTION_PATTERN = re.compile(
    r"(?:§|section|sect\.|clause)\s*(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)
_USB2_PATTERN = re.compile(r"\busb[\s_]*2(?:\.0)?\b", re.IGNORECASE)
_USB3_PATTERN = re.compile(r"\busb[\s_]*3(?:\.[0-2x])?\b", re.IGNORECASE)
_EXPLICIT_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Z0-9_]{2,}|[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|"
    r"[a-z]+[A-Z][A-Za-z0-9]*)\b"
)
_ENUM_TOKEN_PATTERN = re.compile(r"\b[A-Za-z]+\d+[A-Za-z0-9]*\b")
_DOTTED_STATE_PATTERN = re.compile(
    r"\b[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z][A-Za-z0-9]*)+\b"
)
_STATE_PHRASE_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9.-]*)\s+"
    r"(state|mode)\b",
    re.IGNORECASE,
)
_HEX_LITERAL_PATTERN = re.compile(r"\b0x[0-9a-f]+\b", re.IGNORECASE)
_LITERAL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:0x[0-9a-f]+|"
    + _MEASUREMENT_NUMBER_PATTERN
    + r"\s*"
    + _MEASUREMENT_UNIT_PATTERN
    + r"|"
    + _MEASUREMENT_NUMBER_PATTERN
    + r"(?!\s*[%A-Za-z0-9_])|"
    r"zero|one|non[- ]zero|"
    r"enabled|disabled|set|clear|on|off|active|inactive|"
    r"asserted|deasserted|true|false|valid|invalid|present|absent|"
    r"connected|disconnected|powered[- ]?(?:on|off))(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_STANDALONE_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])(?P<number>"
    + _MEASUREMENT_NUMBER_PATTERN
    + r")"
    r"(?![A-Za-z0-9_]|\.\d)",
    re.IGNORECASE,
)
_QUANTITY_NOUN_AFTER_NUMBER_PATTERN = re.compile(
    r"^\s*(?:(?:downstream|upstream|available|supported|valid|current|"
    r"configured|total|maximum|minimum)\s+)*(?:number|count|quantity|"
    r"total|port(?:s)?|entr(?:y|ies)|item(?:s)?|lane(?:s)?|channel(?:s)?|"
    r"state(?:s)?|bit(?:s)?|byte(?:s)?|word(?:s)?|selector(?:s)?|"
    r"code(?:s)?|index|indices|enum(?:eration)?|value(?:s)?|"
    r"configuration|descriptor(?:s)?|transition(?:s)?|time(?:s)?)\b",
    re.IGNORECASE,
)
_QUANTITY_DIRECT_BEFORE_NUMBER_PATTERN = re.compile(
    r"(?:\b(?:number|count|quantity|total|port(?:s)?|entr(?:y|ies)|"
    r"item(?:s)?|lane(?:s)?|channel(?:s)?|state(?:s)?|bit(?:s)?|byte(?:s)?|"
    r"word(?:s)?|selector(?:s)?|code(?:s)?|index|indices|enum(?:eration)?|"
    r"value(?:s)?|configuration|descriptor(?:s)?|minimum|maximum|"
    r"at\s+least|at\s+most|up\s+to)\b|值\s*(?:為|是)?|回傳)"
    r"\s*(?:[:=]\s*)?$",
    re.IGNORECASE,
)
_QUANTITY_RELATION_BEFORE_NUMBER_PATTERN = re.compile(
    r"\b(?:number|count|quantity|total|port(?:s)?|entr(?:y|ies)|"
    r"item(?:s)?|lane(?:s)?|channel(?:s)?|state(?:s)?|bit(?:s)?|byte(?:s)?|"
    r"word(?:s)?|selector(?:s)?|code(?:s)?|index|indices|enum(?:eration)?|"
    r"value(?:s)?|configuration|descriptor(?:s)?|minimum|maximum)\b"
    r"(?:\s+[A-Za-z0-9_./-]+){0,5}\s*"
    r"(?:is|are|equals?|returns?|should\s+be|must\s+be|shall\s+be|"
    r"[:=]|值\s*(?:為|是)?|回傳)\s*$",
    re.IGNORECASE,
)
_CHINESE_QUANTITY_AFTER_NUMBER_PATTERN = re.compile(
    r"^\s*(?:(?:約|大約|至少|至多|最多|最少|共|總共|可用|支援|支持|"
    r"有效|目前)\s*)*"
    r"(?:(?:個|只|條|項|筆|組|張|位|枚|路|門|次|台|件)\s*)?"
    r"(?:(?:下游|上游|下行|上行|可用|支援|支持)\s*)?"
    r"(?:連接埠|埠|端口|接口|通道|lane(?:s)?|port(?:s)?|bit(?:s)?|"
    r"byte(?:s)?|word(?:s)?|channel(?:s)?|item(?:s)?|entry|entries|"
    r"state(?:s)?|value(?:s)?|time(?:s)?|位元(?:組)?|字節|項目|入口|"
    r"條目|狀態|數值|值|選擇器|代碼|索引|轉換|時間)"
    r"(?![\u4e00-\u9fffA-Za-z0-9_])",
    re.IGNORECASE,
)
_CHINESE_QUANTITY_BEFORE_NUMBER_PATTERN = re.compile(
    r"(?:數量|數目|個數|埠數|連接埠數|端口數|總數|數值|值|"
    r"支援|支持|包含|包括|共有|有|可容納|可支援|總計|總共|至少|至多|"
    r"最多|最少|為|是|等於|回傳|返回)\s*(?:[:=為是]|等於)?\s*$",
    re.IGNORECASE,
)
_FIELD_RELATION_PATTERN = re.compile(
    r"(?:!=|=|:|\bis\b|\bequals\b|\breturns?\b|"
    r"\bvalue\s*(?:is|=)?\b|\b(?:should|must|shall)\s+be\b|"
    r"值\s*(?:為|是)?|回傳|不\s*(?:為|是)|非|未)",
    re.IGNORECASE,
)
_STATE_VALUE_ALIASES = {
    "enabled": "enabled",
    "enable": "enabled",
    "啟用": "enabled",
    "已啟用": "enabled",
    "disabled": "disabled",
    "disable": "disabled",
    "停用": "disabled",
    "已停用": "disabled",
    "set": "set",
    "設定": "set",
    "已設定": "set",
    "置位": "set",
    "clear": "clear",
    "清除": "clear",
    "已清除": "clear",
    "清零": "clear",
    "on": "on",
    "開": "on",
    "開啟": "on",
    "已開啟": "on",
    "off": "off",
    "關": "off",
    "關閉": "off",
    "已關閉": "off",
    "active": "active",
    "活動": "active",
    "作用中": "active",
    "inactive": "inactive",
    "未啟用": "inactive",
    "非活動": "inactive",
    "非作用中": "inactive",
    "asserted": "asserted",
    "assert": "asserted",
    "deasserted": "deasserted",
    "解除": "deasserted",
    "未置位": "deasserted",
    "true": "true",
    "真": "true",
    "false": "false",
    "假": "false",
    "valid": "valid",
    "有效": "valid",
    "invalid": "invalid",
    "無效": "invalid",
    "present": "present",
    "存在": "present",
    "absent": "absent",
    "不存在": "absent",
    "connected": "connected",
    "已連線": "connected",
    "已連接": "connected",
    "disconnected": "disconnected",
    "未連線": "disconnected",
    "未連接": "disconnected",
    "powered-on": "powered-on",
    "powered on": "powered-on",
    "上電": "powered-on",
    "通電": "powered-on",
    "powered-off": "powered-off",
    "powered off": "powered-off",
    "斷電": "powered-off",
}
_CLOSED_STATE_VALUES: FrozenSet[str] = frozenset(_STATE_VALUE_ALIASES)
_STATE_VALUE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    + "|".join(
        sorted(
            (re.escape(alias) for alias in _STATE_VALUE_ALIASES),
            key=len,
            reverse=True,
        )
    )
    + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_DIRECT_STATE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:is|are|=|:)|(?:狀態\s*)?(?:為|是))?\s*$",
    re.IGNORECASE,
)
_NEGATION_PATTERN = re.compile(
    r"(?:\b(?:not|never|without|no)\b|不\s*(?:為|是)?|非|未|!)\s*$",
    re.IGNORECASE,
)

_STOP_WORDS: FrozenSet[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "answer",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "does",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "that",
        "this",
        "to",
        "when",
        "which",
        "with",
        "you",
        "your",
        "according",
        "based",
        "current",
        "evidence",
        "provided",
        "response",
        "says",
        "locked",
        "local",
        "model",
        "specification",
        "spec",
        "question",
        "following",
        "must",
        "shall",
        "should",
        "therefore",
        "currently",
    }
)

_GENERIC_TERMS: FrozenSet[str] = frozenset(
    {
        "usb",
        "pdf",
        "phase",
        "corpus",
        "source",
        "sources",
        "document",
        "documents",
        "section",
        "sections",
        "table",
        "tables",
        "value",
        "values",
        "unit",
        "units",
        "require",
        "required",
        "requirement",
        "requirements",
    }
)

_UNIT_TERMS: FrozenSet[str] = frozenset(
    {
        "%",
        "ps",
        "ns",
        "us",
        "ms",
        "pf",
        "mv",
        "uv",
        "v",
        "a",
        "ma",
        "ua",
        "mhz",
        "khz",
        "ghz",
        "ohm",
        "ohms",
        "volt",
        "volts",
        "bit",
        "bits",
    }
)

_SCOPE_TO_SOURCE_IDS = {
    "USB_2_0": frozenset({"usb20_fw", "usb20_se"}),
    "USB_3_X": frozenset({"usb32"}),
    "USB_HUB_COMMON": frozenset(
        {"usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"}
    ),
}
_SCOPE_TO_GENERATION = {
    "USB_2_0": "USB_2_0",
    "USB_3_X": "USB_3_X",
}
_GENERATION_TO_SOURCE_IDS = {
    "USB_2_0": _SCOPE_TO_SOURCE_IDS["USB_2_0"],
    "USB_3_X": _SCOPE_TO_SOURCE_IDS["USB_3_X"],
}
_GENERATION_ORDER = ("USB_2_0", "USB_3_X")


@dataclass(frozen=True)
class EvidenceSelection:
    """The selected subset and load-bearing primary subset of candidates."""

    selected_hits: Tuple[GovernedChunkRetrievalHit, ...]
    primary_hits: Tuple[GovernedChunkRetrievalHit, ...]
    method: str = EVIDENCE_SELECTION_METHOD


@dataclass(frozen=True)
class _CandidateSignal:
    hit: GovernedChunkRetrievalHit
    rank: int
    support_anchors: FrozenSet[str]
    answer_matches: FrozenSet[str]
    question_matches: FrozenSet[str]
    pair_matches: FrozenSet[str]
    generation: str
    score: float


def _normalize(text: str) -> str:
    return " ".join(
        text.casefold()
        .replace("µ", "u")
        .replace("μ", "u")
        .replace("ω", "ohm")
        .replace("|", " ")
        .split()
    )


def _tokens(text: str) -> FrozenSet[str]:
    raw_tokens = _TOKEN_PATTERN.findall(_normalize(text))
    tokens = set(raw_tokens)
    for token in raw_tokens:
        tokens.update(part for part in token.split("/") if len(part) > 1)
    return frozenset(tokens)


def _terms(text: str) -> FrozenSet[str]:
    return frozenset(
        token
        for token in _tokens(text)
        if token not in _STOP_WORDS and len(token) > 1
    )


def _semantic_terms(text: str) -> FrozenSet[str]:
    return frozenset(
        term
        for term in _terms(text)
        if term not in _GENERIC_TERMS
        and term not in _UNIT_TERMS
        and not re.fullmatch(r"\d+(?:\.\d+)?", term)
    )


def _number_unit_pairs(text: str) -> FrozenSet[str]:
    return frozenset(
        match.group(0).replace(" ", "")
        for match in _NUMBER_UNIT_PATTERN.finditer(_normalize(text))
    )


def _unitless_numeric_anchors(text: str) -> FrozenSet[str]:
    """Extract standalone numbers used as counts, codes, or quantities.

    Version and section numbers are excluded structurally. A bare number is
    material only when nearby wording indicates that it carries a quantity or
    enumerated value; ordinary prose numbers remain non-material.
    """
    normalized = _normalize(text)
    anchors = set()
    for match in _STANDALONE_NUMBER_PATTERN.finditer(normalized):
        start, end = match.span("number")
        before = normalized[max(0, start - 64) : start]
        after = normalized[end : min(len(normalized), end + 64)]
        if re.search(r"\busb\s*$", before, re.IGNORECASE):
            continue
        if re.search(r"(?:§|section|sect\.|clause|p\.)\s*$", before, re.IGNORECASE):
            continue
        if re.match(r"\s*%", after):
            continue
        if _NUMBER_UNIT_PATTERN.match(normalized, start):
            continue
        has_before_context = (
            _QUANTITY_DIRECT_BEFORE_NUMBER_PATTERN.search(before) is not None
            or _QUANTITY_RELATION_BEFORE_NUMBER_PATTERN.search(before)
            is not None
            or _CHINESE_QUANTITY_BEFORE_NUMBER_PATTERN.search(before)
            is not None
        )
        has_after_context = (
            _QUANTITY_NOUN_AFTER_NUMBER_PATTERN.match(after) is not None
            or _CHINESE_QUANTITY_AFTER_NUMBER_PATTERN.match(after) is not None
        )
        if not (has_before_context or has_after_context):
            continue
        anchors.add(_normalize(match.group("number")))
    return frozenset(anchors)


def _sections(text: str) -> FrozenSet[str]:
    return frozenset(_SECTION_PATTERN.findall(text))


def _explicit_identifier_tokens(text: str) -> FrozenSet[str]:
    return frozenset(
        token
        for token in (
            _normalize(match.group(0))
            for match in _EXPLICIT_IDENTIFIER_PATTERN.finditer(text)
        )
        if token not in _STOP_WORDS and token not in _GENERIC_TERMS
    )


def _enum_tokens(text: str) -> FrozenSet[str]:
    return frozenset(
        token
        for token in (
            _normalize(match.group(0))
            for match in _ENUM_TOKEN_PATTERN.finditer(text)
        )
        if token not in _STOP_WORDS and token not in _GENERIC_TERMS
    )


def _dotted_state_tokens(text: str) -> FrozenSet[str]:
    return frozenset(
        _normalize(match.group(0))
        for match in _DOTTED_STATE_PATTERN.finditer(text)
    )


def _state_phrases(text: str) -> FrozenSet[str]:
    return frozenset(
        f"{_normalize(match.group(1))} {_normalize(match.group(2))}"
        for match in _STATE_PHRASE_PATTERN.finditer(text)
        if "_" not in match.group(1)
    )


def _canonical_state_value(value: str) -> Optional[str]:
    normalized = _normalize(value)
    return _STATE_VALUE_ALIASES.get(normalized) or _STATE_VALUE_ALIASES.get(
        normalized.replace(" ", "")
    )


def _field_value_anchors(text: str) -> FrozenSet[str]:
    anchors = set()
    identifier_matches = [
        match
        for match in _EXPLICIT_IDENTIFIER_PATTERN.finditer(text)
        if _normalize(match.group(0)) not in _STOP_WORDS
        and _normalize(match.group(0)) not in _GENERIC_TERMS
        and _normalize(match.group(0)) not in _CLOSED_STATE_VALUES
    ]
    for index, field_match in enumerate(identifier_matches):
        field = _normalize(field_match.group(0))
        segment_end = (
            identifier_matches[index + 1].start()
            if index + 1 < len(identifier_matches)
            else len(text)
        )
        # Bind a value only within the field's own segment. In particular,
        # ``PORT_POWER is distinct from PORT_RESET = 4`` must not produce a
        # false ``port_power=4`` pair by crossing the PORT_RESET identifier.
        segment = text[field_match.end() : segment_end]
        relation = _FIELD_RELATION_PATTERN.search(segment)
        if relation is None:
            value_text = ""
            relation_negated = False
        else:
            value_text = segment[relation.end() :]
            relation_text = segment[relation.start() : relation.end()]
            relation_negated = (
                relation_text.strip().startswith("!=")
                or _NEGATION_PATTERN.search(relation_text) is not None
            )
            for literal in _LITERAL_PATTERN.finditer(value_text):
                value = _canonical_state_value(literal.group(0)) or _normalize(
                    literal.group(0)
                ).replace(" ", "")
                if relation_negated or _NEGATION_PATTERN.search(
                    value_text[: literal.start()]
                ):
                    value = f"not:{value}"
                anchors.add(f"{field}={value}")

        for state_match in _STATE_VALUE_PATTERN.finditer(segment):
            prefix = segment[: state_match.start()]
            negation = _NEGATION_PATTERN.search(prefix)
            direct_prefix = prefix[: negation.start()] if negation else prefix
            if _DIRECT_STATE_PREFIX_PATTERN.fullmatch(direct_prefix) is None:
                continue
            state = _canonical_state_value(state_match.group(0))
            if state is not None:
                if relation_negated or negation is not None:
                    state = f"not:{state}"
                anchors.add(f"{field}={state}")
    return frozenset(anchors)


def _generation_anchors(text: str) -> FrozenSet[str]:
    generations = set()
    if _USB2_PATTERN.search(text):
        generations.add("USB_2_0")
    if _USB3_PATTERN.search(text):
        generations.add("USB_3_X")
    return frozenset(generations)


def _material_answer_anchors(question: str, answer: str) -> FrozenSet[str]:
    """Extract answer literals that must be present in candidate evidence.

    Ordinary prose overlap is intentionally excluded. These anchors are the
    load-bearing literals for which a citation must provide direct lexical
    support; dropping one because no candidate contains it would otherwise
    let a wrong value inherit support from a matching topic name.
    """
    anchors = set(_number_unit_pairs(answer))
    anchors.update(_unitless_numeric_anchors(answer))
    anchors.update(
        _normalize(match.group(0))
        for match in _HEX_LITERAL_PATTERN.finditer(answer)
    )
    anchors.update(_sections(answer))
    anchors.update(_explicit_identifier_tokens(answer))
    anchors.update(_enum_tokens(answer))
    anchors.update(_dotted_state_tokens(answer))
    anchors.update(_state_phrases(answer))
    anchors.update(_field_value_anchors(answer))
    anchors.update(_generation_anchors(answer))
    return frozenset(anchors)


def _material_candidate_anchors(hit: GovernedChunkRetrievalHit) -> FrozenSet[str]:
    """Return literals and provenance anchors exposed by one candidate."""
    anchors = set(_content_anchors(hit.chunk.content))
    anchors.update(_number_unit_pairs(hit.chunk.content))
    anchors.update(_unitless_numeric_anchors(hit.chunk.content))
    anchors.update(
        _normalize(match.group(0))
        for match in _HEX_LITERAL_PATTERN.finditer(hit.chunk.content)
    )
    anchors.add(_normalize(hit.chunk.section))
    anchors.update(_explicit_identifier_tokens(hit.chunk.content))
    anchors.update(_enum_tokens(hit.chunk.content))
    anchors.update(_dotted_state_tokens(hit.chunk.content))
    anchors.update(_state_phrases(hit.chunk.content))
    anchors.update(_field_value_anchors(hit.chunk.content))
    generation = _candidate_generation(hit)
    if generation != "UNKNOWN":
        anchors.add(generation)
    return frozenset(anchors)


def _requested_generations(question: str) -> FrozenSet[str]:
    return _generation_anchors(question)


def _ordered_generations(generations: Iterable[str]) -> Tuple[str, ...]:
    return tuple(
        generation for generation in _GENERATION_ORDER if generation in generations
    )


def _material_answer_anchors_by_generation(
    question: str,
    answer: str,
    requested_generations: FrozenSet[str],
) -> dict[str, FrozenSet[str]]:
    """Associate answer literals with the generation that claims them.

    A global literal union is insufficient for a comparison answer: it could
    accept USB 2.0's value from a USB 3.2 candidate and vice versa. When the
    answer explicitly introduces multiple generations, each generation's
    clause becomes its own conservative anchor scope. Unscoped material is
    required from every requested generation rather than silently assigned to
    whichever candidate happens to contain it.
    """
    all_anchors = _material_answer_anchors(question, answer)
    if not requested_generations:
        return {}

    answer_generations = _generation_anchors(answer)
    if len(answer_generations) < 2:
        return {
            generation: all_anchors for generation in requested_generations
        }

    occurrences = []
    for generation, pattern in (
        ("USB_2_0", _USB2_PATTERN),
        ("USB_3_X", _USB3_PATTERN),
    ):
        occurrences.extend(
            (match.start(), match.end(), generation)
            for match in pattern.finditer(answer)
        )
    occurrences.sort()
    scoped: dict[str, set[str]] = {
        generation: set() for generation in requested_generations
    }
    covered: set[str] = set()
    index = 0
    while index < len(occurrences):
        start = occurrences[index][0]
        group_end = index + 1
        while group_end < len(occurrences):
            previous_end = occurrences[group_end - 1][1]
            next_start = occurrences[group_end][0]
            between = answer[previous_end:next_start]
            if not re.fullmatch(
                r"\s*(?:(?:and|or|與|和|及|以及|或)\s*)?"
                r"[\s,、，;/&+]*\s*",
                between,
                re.IGNORECASE,
            ):
                break
            group_end += 1

        end = (
            occurrences[group_end][0]
            if group_end < len(occurrences)
            else len(answer)
        )
        segment_anchors = _material_answer_anchors(
            question,
            answer[start:end],
        )
        segment_generations = _generation_anchors(answer[start:end])
        covered.update(segment_anchors)
        shared_anchors = segment_anchors - segment_generations
        for _, _, generation in occurrences[index:group_end]:
            if generation not in scoped:
                continue
            scoped[generation].update(shared_anchors)
            scoped[generation].add(generation)
        index = group_end

    # Material text outside an explicitly generation-labelled clause is
    # shared/ambiguous. Require it in every requested generation instead of
    # allowing a union to mask a swapped claim.
    unscoped = all_anchors - covered
    for generation in scoped:
        scoped[generation].update(unscoped)
    return {generation: frozenset(anchors) for generation, anchors in scoped.items()}


def _candidate_generation(hit: GovernedChunkRetrievalHit) -> str:
    if hit.chunk.source_id in {"usb20_fw", "usb20_se"}:
        return "USB_2_0"
    if hit.chunk.source_id in {"usb32", "superspeed_hub_lvs"}:
        return "USB_3_X"
    return "UNKNOWN"


def _answer_anchors(question: str, answer: str) -> FrozenSet[str]:
    question_terms = _semantic_terms(question)
    answer_terms = _semantic_terms(answer)
    anchors = set(answer_terms & question_terms)
    anchors.update(
        term
        for term in answer_terms
        if "_" in term
        or (any(char.isdigit() for char in term) and any(char.isalpha() for char in term))
    )
    anchors.update(_sections(question))
    anchors.update(_sections(answer))
    anchors.update(
        pair
        for pair in _number_unit_pairs(answer)
        if not pair.endswith("%")
    )
    anchors.update(_material_answer_anchors(question, answer))

    combined = f"{question} {answer}"
    if re.search(
        r"\b(?:address|configured|configuration|bit|bits|state|status)\b",
        combined,
        re.IGNORECASE,
    ):
        numeric_words = {"0": "zero", "1": "one"}
        for token in _tokens(combined):
            if token in numeric_words:
                anchors.add(numeric_words[token])
            elif token in {"zero", "one"}:
                anchors.add(token)
    return frozenset(anchors)


def _content_anchors(text: str) -> FrozenSet[str]:
    tokens = set(_tokens(text))
    if "0" in tokens:
        tokens.add("zero")
    if "zero" in tokens:
        tokens.add("0")
    if "1" in tokens:
        tokens.add("one")
    if "one" in tokens:
        tokens.add("1")
    return frozenset(tokens)


def _signal_for_candidate(
    question: str,
    answer: str,
    hit: GovernedChunkRetrievalHit,
    rank: int,
    anchors: FrozenSet[str],
) -> _CandidateSignal:
    answer_terms = _semantic_terms(answer)
    question_terms = _semantic_terms(question)
    content_terms = _content_anchors(hit.chunk.content) | _material_candidate_anchors(hit)
    section_matches = _sections(answer) & {hit.chunk.section}
    section_matches |= _sections(question) & {hit.chunk.section}
    answer_matches = (answer_terms & content_terms) | section_matches
    question_matches = question_terms & content_terms
    answer_pairs = {
        pair for pair in _number_unit_pairs(answer) if not pair.endswith("%")
    }
    candidate_pairs = _number_unit_pairs(hit.chunk.content)
    pair_matches = answer_pairs & candidate_pairs
    support_anchors = (anchors & content_terms) | pair_matches | section_matches
    identifier_matches = {
        term
        for term in answer_matches
        if "_" in term
        or (any(char.isdigit() for char in term) and any(char.isalpha() for char in term))
    }
    score = (
        8.0 * len(pair_matches)
        + 4.0 * len(section_matches)
        + 3.0 * len(identifier_matches)
        + 1.5 * len(answer_matches)
        + 0.5 * len(question_matches)
    )
    if not support_anchors:
        score = 0.0
    return _CandidateSignal(
        hit=hit,
        rank=rank,
        support_anchors=frozenset(support_anchors),
        answer_matches=frozenset(answer_matches),
        question_matches=frozenset(question_matches),
        pair_matches=frozenset(pair_matches),
        generation=_candidate_generation(hit),
        score=score,
    )


def _select_group(
    signals: Sequence[_CandidateSignal],
    anchors: FrozenSet[str],
    required_anchors: FrozenSet[str] = frozenset(),
) -> Tuple[_CandidateSignal, ...]:
    available = [signal for signal in signals if signal.support_anchors]
    if not available:
        return ()

    covered_by_group = set().union(
        *(signal.support_anchors for signal in available)
    )
    if not required_anchors.issubset(covered_by_group):
        return ()
    required = set(anchors)
    required.update(required_anchors)
    required &= covered_by_group
    if not required:
        best = max(available, key=lambda signal: (signal.score, -signal.rank))
        return (best,)

    selected: List[_CandidateSignal] = []
    uncovered = set(required)
    remaining = list(available)
    while uncovered:
        best = max(
            remaining,
            key=lambda signal: (
                len(signal.support_anchors & uncovered),
                signal.score,
                -signal.rank,
            ),
            default=None,
        )
        if best is None or not (best.support_anchors & uncovered):
            return ()
        selected.append(best)
        uncovered -= best.support_anchors
        remaining.remove(best)

    return tuple(selected)


def _add_numeric_table_support(
    selected: Sequence[_CandidateSignal],
    available: Sequence[_CandidateSignal],
) -> Tuple[_CandidateSignal, ...]:
    """Add close table corroboration when the answer contains a value pair.

    A table with an answer value/unit pair is a distinct, useful evidence
    form even when a nearby paragraph already covers the same lexical anchors.
    Restricting this addition to tables with an exact answer pair prevents
    unrelated same-topic paragraphs from becoming formal citations.
    """
    if not selected:
        return tuple(selected)
    highest_score = max(signal.score for signal in available)
    selected_ids = {signal.hit.chunk.chunk_id for signal in selected}
    table_support = [
        signal
        for signal in available
        if signal.hit.chunk.chunk_id not in selected_ids
        and signal.hit.chunk.chunk_kind == "table"
        and signal.pair_matches
        and signal.score >= highest_score * 0.50
    ]
    return tuple(selected) + tuple(table_support)


def _choose_primary(
    selected: Sequence[_CandidateSignal],
    requested_generations: FrozenSet[str],
) -> Tuple[GovernedChunkRetrievalHit, ...]:
    if not selected:
        return ()

    groups: Iterable[Sequence[_CandidateSignal]]
    if requested_generations:
        groups = (
            [signal for signal in selected if signal.generation == generation]
            for generation in requested_generations
        )
    else:
        groups = (selected,)

    primary_signals: List[_CandidateSignal] = []
    for group in groups:
        group = list(group)
        if not group:
            continue
        highest_score = max(signal.score for signal in group)
        group_primary = []
        for signal in group:
            other_coverage = set().union(
                *(other.support_anchors for other in group if other is not signal)
            )
            if (
                signal.support_anchors - other_coverage
                or signal.score >= highest_score * 0.70
            ):
                group_primary.append(signal)
        if not group_primary:
            group_primary.append(
                max(group, key=lambda signal: (signal.score, -signal.rank))
            )
        primary_signals.extend(group_primary)

    primary_ids = {signal.hit.chunk.chunk_id for signal in primary_signals}
    return tuple(
        signal.hit
        for signal in sorted(selected, key=lambda item: item.rank)
        if signal.hit.chunk.chunk_id in primary_ids
    )


def select_evidence(
    question: str,
    answer: str | None,
    hits: Sequence[GovernedChunkRetrievalHit],
    *,
    required_scopes: Optional[Sequence[str]] = None,
) -> EvidenceSelection:
    """Select evidence with deterministic lexical support signals.

    This is a display/provenance selector, not semantic entailment. It returns
    no selected evidence for the prescribed model abstention sentinel.
    """
    if (
        not question.strip()
        or not answer
        or answer.lstrip().startswith("INSUFFICIENT_EVIDENCE")
        or not hits
    ):
        return EvidenceSelection((), ())

    anchors = _answer_anchors(question, answer)
    requested_generations = _requested_generations(question)
    scope_groups = {}
    if required_scopes:
        for scope in required_scopes:
            normalized_scope = str(scope).strip()
            source_ids = _SCOPE_TO_SOURCE_IDS.get(normalized_scope)
            if not source_ids:
                return EvidenceSelection((), ())
            scope_groups[normalized_scope] = source_ids
    required_scope_generations = frozenset(
        _SCOPE_TO_GENERATION[scope]
        for scope in scope_groups
        if scope in _SCOPE_TO_GENERATION
    )
    selection_generations = frozenset(
        requested_generations
        | _generation_anchors(answer)
        | required_scope_generations
    )
    material_anchors_by_generation = _material_answer_anchors_by_generation(
        question,
        answer,
        selection_generations,
    )
    material_anchors = _material_answer_anchors(question, answer)
    signals = [
        _signal_for_candidate(question, answer, hit, rank, anchors)
        for rank, hit in enumerate(hits, start=1)
        if (
            (not scope_groups and not selection_generations)
            or (
                scope_groups
                and any(hit.chunk.source_id in source_ids for source_ids in scope_groups.values())
            )
            or (
                not scope_groups
                and _candidate_generation(hit) in selection_generations
            )
        )
    ]

    if scope_groups:
        groups = []
        for scope, source_ids in scope_groups.items():
            if scope == "USB_HUB_COMMON" and selection_generations:
                scope_generations = _ordered_generations(selection_generations)
            elif scope in _SCOPE_TO_GENERATION:
                scope_generations = (_SCOPE_TO_GENERATION[scope],)
            else:
                scope_generations = (None,)
            for generation in scope_generations:
                eligible_source_ids = set(source_ids)
                if generation is not None:
                    eligible_source_ids &= set(
                        _GENERATION_TO_SOURCE_IDS.get(generation, ())
                    )
                groups.append(
                    (
                        scope,
                        generation,
                        [
                            signal
                            for signal in signals
                            if signal.hit.chunk.source_id in eligible_source_ids
                        ],
                    )
                )
        if any(not group for _scope, _generation, group in groups):
            return EvidenceSelection((), ())
    elif selection_generations:
        groups = [
            (
                None,
                generation,
                [signal for signal in signals if signal.generation == generation],
            )
            for generation in _ordered_generations(selection_generations)
        ]
        if any(not group for _scope, _generation, group in groups):
            return EvidenceSelection((), ())
    else:
        groups = [(None, None, signals)]

    selected_signals: List[_CandidateSignal] = []
    for scope, generation, group in groups:
        required_anchors = (
            material_anchors_by_generation[generation]
            if generation is not None and generation in material_anchors_by_generation
            else material_anchors
        )
        selected = _select_group(group, anchors, required_anchors)
        if not selected:
            return EvidenceSelection((), ())
        selected_signals.extend(_add_numeric_table_support(selected, group))

    selected_ids = {signal.hit.chunk.chunk_id for signal in selected_signals}
    selected_hits = tuple(
        hit for hit in hits if hit.chunk.chunk_id in selected_ids
    )
    primary_hits = _choose_primary(selected_signals, selection_generations)
    return EvidenceSelection(selected_hits, primary_hits)
