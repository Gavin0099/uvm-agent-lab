"""Deterministic selection of answer-supporting evidence candidates.

The local model does not emit citation IDs, so this module deliberately does
not claim to observe the model's internal evidence use. It produces an
explainable lexical set-cover selection from retrieved candidates for UI
citation projection only. Semantic entailment remains outside this
development path.

Evidence Selection v1 is intentionally grammar-bounded. It supports explicit
literal anchors, identifier/value relations, signed/scientific measurements,
ordered measurement ranges, recognized closed states, USB generation/scope
binding, and a conservative polarity guard for simple prose claims. It does
not attempt general natural-language understanding. If an answer has no
recognized v1 binding, or uses an unsupported qualifier, this module returns an
empty selection so the adapter can surface ``MISSING_EVIDENCE``; it never
promotes a best-effort topic match to a formal citation.

The only topic-only exception is an identifier paired with the recognized
``state``/``status`` vocabulary used by the existing cross-scope contract.
Multiple unbound quantity numbers are ambiguous in v1 and fail closed. Table
supplements must carry the answer's field/value anchor when one exists; v1 does
not parse serialized table rows. An explicit identifier followed by a literal
must use a recognized field/value relation; unsupported predicate prose fails
closed instead of borrowing a topic citation.

Percentage literals and ``between`` ranges are intentionally unsupported in
v1. They are rejected rather than partially interpreted until a separate
contract change adds their grammar and regression coverage.

Adding another language form requires a separate contract decision and a
negative regression. Reviewer-discovered phrasing outside this grammar is a
fail-closed case, not an automatic request to add another regular expression.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Sequence, Tuple

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
_MEASUREMENT_LABEL_ALIASES = {
    "rise time": "rise_time",
    "rising time": "rise_time",
    "rise": "rise_time",
    "上升時間": "rise_time",
    "上升": "rise_time",
    "fall time": "fall_time",
    "falling time": "fall_time",
    "fall": "fall_time",
    "下降時間": "fall_time",
    "下降": "fall_time",
}
_MEASUREMENT_LABEL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    + "|".join(
        sorted(
            (re.escape(label) for label in _MEASUREMENT_LABEL_ALIASES),
            key=len,
            reverse=True,
        )
    )
    + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_NUMBER_UNIT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    + _MEASUREMENT_NUMBER_PATTERN
    + r"\s*"
    + _MEASUREMENT_UNIT_PATTERN
    + r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_MEASUREMENT_RANGE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?P<lower>"
    + _MEASUREMENT_NUMBER_PATTERN
    + r")\s*(?:to|through|至|到|~|～|[-–—])\s*(?P<upper>"
    + _MEASUREMENT_NUMBER_PATTERN
    + r")\s*(?P<unit>"
    + _MEASUREMENT_UNIT_PATTERN
    + r")(?![A-Za-z0-9_])",
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
_TOPIC_DESCRIPTOR_PATTERN = re.compile(
    r"\b(?:state|states|status|requirement|requirements)\b|"
    r"狀態|狀態碼|要求|需求",
    re.IGNORECASE,
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
_IDENTIFIER_QUANTITY_RELATION_PATTERN = re.compile(
    r"(?:\b(?:supports?|provides?|has|contains?|includes?|allows?|"
    r"returns?|equals?|up\s+to)\b|支援|支持|包含|包括|共有|有|"
    r"可容納|可支援|回傳|返回|等於|[:=])\s*$",
    re.IGNORECASE,
)
_FIELD_DESCRIPTOR_WORDS: FrozenSet[str] = frozenset(
    {
        "a",
        "an",
        "allowable",
        "class",
        "configuration",
        "current",
        "default",
        "descriptor",
        "feature",
        "field",
        "fields",
        "has",
        "have",
        "hub",
        "includes",
        "input",
        "its",
        "maximum",
        "minimum",
        "of",
        "option",
        "options",
        "output",
        "port",
        "reset",
        "selector",
        "selectors",
        "setting",
        "settings",
        "state",
        "status",
        "the",
        "value",
        "values",
    }
)
_FIELD_VALUE_LEAD_WORDS: FrozenSet[str] = frozenset(
    {
        "a",
        "an",
        "at",
        "current",
        "currently",
        "equal",
        "fewer",
        "greater",
        "least",
        "less",
        "more",
        "most",
        "no",
        "not",
        "of",
        "or",
        "the",
        "than",
        "to",
        "equals",
        "returns",
    }
)
_FIELD_DESCRIPTOR_CHARS = frozenset(
    "的之其該這那特徵選擇器數值值狀態欄位字段功能都均皆"
)
_COMPARISON_QUALIFIER_ALIASES = {
    "less than or equal to": "le",
    "less than or equal": "le",
    "greater than or equal to": "ge",
    "greater than or equal": "ge",
    "not greater than": "le",
    "not less than": "ge",
    "no greater than": "le",
    "no less than": "ge",
    "no more than": "le",
    "no fewer than": "ge",
    "at most": "le",
    "at least": "ge",
    "less than": "lt",
    "greater than": "gt",
    "below": "lt",
    "under": "lt",
    "above": "gt",
    "over": "gt",
    "小於等於": "le",
    "小於或等於": "le",
    "大於等於": "ge",
    "大於或等於": "ge",
    "不大於": "le",
    "不超過": "le",
    "至多": "le",
    "不小於": "ge",
    "不低於": "ge",
    "至少": "ge",
    "小於": "lt",
    "少於": "lt",
    "低於": "lt",
    "大於": "gt",
    "多於": "gt",
    "高於": "gt",
    "<=": "le",
    "≤": "le",
    "<": "lt",
    ">=": "ge",
    "≥": "ge",
    ">": "gt",
}
_COMPARISON_QUALIFIER_PATTERN = re.compile(
    r"(?P<qualifier>(?:"
    + "|".join(
        sorted(
            (re.escape(qualifier) for qualifier in _COMPARISON_QUALIFIER_ALIASES),
            key=len,
            reverse=True,
        )
    )
    + r"))\s*$",
    re.IGNORECASE,
)
_FIELD_RELATION_PATTERN = re.compile(
    r"(?:!=|<=|>=|≤|≥|<|>|=|:|\bis\b|\bequals\b|\breturns?\b|"
    r"\bvalue\s*(?:is|=)?\b|\b(?:should|must|shall)\s+be\b|"
    r"值\s*(?:為|是)?|回傳|(?<![\u4e00-\u9fff])(?:都|均|皆)?\s*(?:為|是)|"
    r"不\s*(?:為|是))",
    re.IGNORECASE,
)
_PROSE_NEGATION_PATTERN = re.compile(
    r"(?:\b(?:not|never|without|no|cannot|can't|doesn't|don't|isn't|"
    r"aren't|wasn't|weren't|hasn't|haven't|won't|didn't|couldn't|"
    r"wouldn't|shouldn't|mustn't|needn't|mightn't|oughtn't|shan't)\b|"
    r"\b(?:does|do|did|is|are|was|were|has|have|will|could|would|"
    r"should|must|need|might|ought|shall)\s+not\b|"
    r"不\s*(?:支援|支持|是|為)?|未\s*(?:支援|支持|啟用|啟動)?|"
    r"沒有|無法|不可|禁止|非(?!零))",
    re.IGNORECASE,
)
_PROSE_NEGATION_TERMS: FrozenSet[str] = frozenset(
    {
        "not",
        "never",
        "without",
        "no",
        "cannot",
        "cant",
        "doesnt",
        "dont",
        "didnt",
        "isnt",
        "arent",
        "wasnt",
        "werent",
        "hasnt",
        "havent",
        "wont",
        "couldnt",
        "wouldnt",
        "shouldnt",
        "mustnt",
        "neednt",
        "mightnt",
        "oughtnt",
        "shant",
        "不",
        "未",
        "沒有",
        "無法",
        "不可",
        "禁止",
        "非",
    }
)
_CONTRACTED_NEGATION_PATTERN = re.compile(
    r"\b(?:isn['’]t|aren['’]t|wasn['’]t|weren['’]t|hasn['’]t|"
    r"haven['’]t|hadn['’]t|doesn['’]t|don['’]t|didn['’]t|"
    r"can['’]t|couldn['’]t|won['’]t|wouldn['’]t|shouldn['’]t|"
    r"mustn['’]t|needn['’]t|mightn['’]t|oughtn['’]t|shan['’]t)\b",
    re.IGNORECASE,
)
_PROSE_AUXILIARY_TERMS: FrozenSet[str] = frozenset(
    {
        "can",
        "could",
        "do",
        "does",
        "did",
        "had",
        "has",
        "have",
        "is",
        "are",
        "was",
        "were",
        "will",
        "would",
        "might",
        "need",
        "ought",
    }
)
_PROSE_CLAIM_TERM_PATTERNS = {
    "support": re.compile(r"(?:支援|支持)", re.IGNORECASE),
}
_UNSUPPORTED_CLAIM_MARKER_PATTERN = re.compile(
    r"\b(?:ought|ideally|approximately|approx\.?|roughly|around|about|"
    r"preferably|typically|generally|possibly|maybe|perhaps)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_PERCENT_PATTERN = re.compile(r"[%％]")
_UNSUPPORTED_RANGE_MARKER_PATTERN = re.compile(r"\bbetween\b", re.IGNORECASE)
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


def _is_bounded_field_text(text: str, allowed_words: FrozenSet[str]) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return True
    remaining = normalized
    for word in allowed_words:
        remaining = re.sub(
            rf"(?<![a-z0-9_]){re.escape(word)}(?![a-z0-9_])",
            " ",
            remaining,
        )
    remaining = re.sub(r"[\s,:=()\[\]]+", "", remaining)
    return not remaining or all(
        character in _FIELD_DESCRIPTOR_CHARS for character in remaining
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


def _measurement_range_anchor(match: re.Match[str]) -> str:
    lower = _normalize(match.group("lower")).replace(" ", "")
    upper = _normalize(match.group("upper")).replace(" ", "")
    unit = _normalize(match.group("unit")).replace(" ", "")
    return f"range:{lower}..{upper}{unit}"


def _measurement_range_anchors(text: str) -> FrozenSet[str]:
    return frozenset(
        _measurement_range_anchor(match)
        for match in _MEASUREMENT_RANGE_PATTERN.finditer(_normalize(text))
    )


def _claim_term(term: str) -> str:
    aliases = {
        "supports": "support",
        "supported": "support",
        "supporting": "support",
        "provides": "provide",
        "provided": "provide",
        "providing": "provide",
        "requires": "require",
        "required": "require",
        "requiring": "require",
    }
    return aliases.get(term, term)


def _prose_claim_polarities(text: str) -> dict[str, FrozenSet[str]]:
    """Return normalized claim signatures and their observed polarity.

    This deliberately covers only clauses with at least two semantic terms.
    It is a polarity guard for ordinary prose, not a general natural-language
    parser or semantic entailment implementation.
    """
    normalized = _normalize(text)
    for contraction, expansion in {
        "doesn't": "does not",
        "doesn’t": "does not",
        "don't": "do not",
        "don’t": "do not",
        "didn't": "did not",
        "didn’t": "did not",
        "isn't": "is not",
        "isn’t": "is not",
        "aren't": "are not",
        "aren’t": "are not",
        "wasn't": "was not",
        "wasn’t": "was not",
        "weren't": "were not",
        "weren’t": "were not",
        "hasn't": "has not",
        "hasn’t": "has not",
        "haven't": "have not",
        "haven’t": "have not",
        "can't": "cannot",
        "can’t": "cannot",
        "couldn't": "could not",
        "couldn’t": "could not",
        "won't": "will not",
        "won’t": "will not",
        "wouldn't": "would not",
        "wouldn’t": "would not",
        "shouldn't": "should not",
        "shouldn’t": "should not",
        "mustn't": "must not",
        "mustn’t": "must not",
        "needn't": "need not",
        "needn’t": "need not",
        "mightn't": "might not",
        "mightn’t": "might not",
        "oughtn't": "ought not",
        "oughtn’t": "ought not",
        "shan't": "shall not",
        "shan’t": "shall not",
    }.items():
        normalized = normalized.replace(contraction, expansion)

    claims: dict[str, set[str]] = {}
    for clause in re.split(r"[.;!?；，。！？\n]+", normalized):
        clause = clause.strip()
        if not clause:
            continue
        terms = {
            _claim_term(term)
            for term in _semantic_terms(clause)
            if term not in _PROSE_NEGATION_TERMS
            and term not in _PROSE_AUXILIARY_TERMS
        }
        terms.update(
            canonical_term
            for canonical_term, pattern in _PROSE_CLAIM_TERM_PATTERNS.items()
            if pattern.search(clause)
        )
        if len(terms) < 2:
            continue
        signature = "|".join(sorted(terms))
        polarity = (
            "negative"
            if _PROSE_NEGATION_PATTERN.search(clause)
            else "positive"
        )
        claims.setdefault(signature, set()).add(polarity)
    return {signature: frozenset(polarities) for signature, polarities in claims.items()}


def _prose_negation_anchors(text: str) -> FrozenSet[str]:
    return frozenset(
        f"prose_claim:negative:{signature}"
        for signature, polarities in _prose_claim_polarities(text).items()
        if "negative" in polarities
    )


def _prose_polarity_conflict(answer: str, candidate: str) -> bool:
    answer_claims = _prose_claim_polarities(answer)
    candidate_claims = _prose_claim_polarities(candidate)
    for signature, answer_polarities in answer_claims.items():
        candidate_polarities = candidate_claims.get(signature, frozenset())
        if (
            "negative" in answer_polarities
            and "positive" in candidate_polarities
        ) or (
            "positive" in answer_polarities
            and "negative" in candidate_polarities
        ):
            return True
    return False


def _has_supported_v1_binding(answer: str) -> bool:
    """Return whether the answer contains a bounded v1 citation signal."""
    if (
        _UNSUPPORTED_CLAIM_MARKER_PATTERN.search(answer)
        or _UNSUPPORTED_PERCENT_PATTERN.search(answer)
        or _UNSUPPORTED_RANGE_MARKER_PATTERN.search(answer)
        or _has_unsupported_contracted_field_negation(answer)
        or _has_unbound_identifier_literal_claim(answer)
    ):
        return False
    if len(_unitless_numeric_anchors(answer)) > 1:
        # v1 intentionally does not infer which of several bare numbers
        # belongs to which quantity label. A future count-binding grammar may
        # admit this shape; until then it must abstain rather than accept a
        # swapped-count citation.
        return False
    return bool(
        _number_unit_pairs(answer)
        or _measurement_range_anchors(answer)
        or _measurement_value_anchors(answer)
        or _unitless_numeric_anchors(answer)
        or _HEX_LITERAL_PATTERN.search(answer)
        or _sections(answer)
        or _field_value_anchors(answer)
        or _prose_negation_anchors(answer)
        or _topic_state_anchors(answer)
    )


def _comparison_qualifier(text: str) -> Optional[str]:
    match = _COMPARISON_QUALIFIER_PATTERN.search(_normalize(text))
    if match is None:
        return None
    return _COMPARISON_QUALIFIER_ALIASES.get(
        _normalize(match.group("qualifier"))
    )


def _measurement_value_anchors(text: str) -> FrozenSet[str]:
    """Bind measurement literals to a nearby rise/fall quantity label.

    The unbound number/unit anchors remain useful for ordinary factual values,
    but answers containing multiple same-unit quantities need a second,
    label-bound anchor so swapped values cannot inherit mutual support.
    """
    normalized = _normalize(text)
    anchors = set()
    for value_match in _NUMBER_UNIT_PATTERN.finditer(normalized):
        before = normalized[: value_match.start()]
        boundary_matches = list(re.finditer(r"[.;,!?；，。！？\n]", before))
        clause_start = boundary_matches[-1].end() if boundary_matches else 0
        clause = normalized[clause_start : value_match.start()]
        label_matches = list(_MEASUREMENT_LABEL_PATTERN.finditer(clause))
        if not label_matches:
            continue
        label_match = label_matches[-1]
        label = _MEASUREMENT_LABEL_ALIASES.get(
            _normalize(label_match.group(0))
        )
        if label is None:
            continue
        qualifier = _comparison_qualifier(clause[label_match.end() :])
        value = _normalize(value_match.group(0)).replace(" ", "")
        if qualifier is not None:
            value = f"{qualifier}:{value}"
        anchors.add(f"{label}={value}")
    return frozenset(anchors)


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


def _topic_state_anchors(text: str) -> FrozenSet[str]:
    """Extract the bounded ``identifier + state/status`` topic form.

    This is the only topic-only form retained by v1 for the explicit
    cross-scope state comparison. Arbitrary identifier-plus-predicate prose is
    not a binding and must fail closed.
    """
    identifiers = list(_EXPLICIT_IDENTIFIER_PATTERN.finditer(text))
    anchors = set()
    for index, identifier_match in enumerate(identifiers):
        identifier = _normalize(identifier_match.group(0))
        if identifier in _STOP_WORDS or identifier in _GENERIC_TERMS:
            continue
        segment_end = (
            identifiers[index + 1].start()
            if index + 1 < len(identifiers)
            else len(text)
        )
        segment = text[identifier_match.end() : segment_end]
        descriptor = _TOPIC_DESCRIPTOR_PATTERN.search(segment)
        if descriptor is None:
            continue
        anchors.add(f"{identifier}=topic:{_normalize(descriptor.group(0))}")
    return frozenset(anchors)


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


def _is_terminal_state_value_identifier(
    text: str,
    identifier_match: re.Match[str],
) -> bool:
    prefix = text[: identifier_match.start()]
    return bool(
        _state_phrases(prefix)
        and _TOPIC_DESCRIPTOR_PATTERN.search(prefix)
    )


def _canonical_state_value(value: str) -> Optional[str]:
    normalized = _normalize(value)
    return _STATE_VALUE_ALIASES.get(normalized) or _STATE_VALUE_ALIASES.get(
        normalized.replace(" ", "")
    )


def _field_relation_for_first_literal(
    segment: str,
) -> Optional[Tuple[re.Match[str], Tuple[int, int]]]:
    literal_span = _first_v1_literal_span(segment)
    if literal_span is None:
        return None
    relation = _FIELD_RELATION_PATTERN.search(segment)
    if relation is None or relation.start() >= literal_span[0]:
        return None
    if not _is_bounded_field_text(
        segment[: relation.start()], _FIELD_DESCRIPTOR_WORDS
    ):
        return None
    if not _is_bounded_field_text(
        segment[relation.end() : literal_span[0]],
        _FIELD_VALUE_LEAD_WORDS,
    ):
        return None
    return relation, literal_span


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
        relation_info = _field_relation_for_first_literal(segment)
        if relation_info is None:
            value_text = ""
            relation_negated = False
        else:
            relation, literal_span = relation_info
            value_text = segment[relation.end() :]
            relation_text = segment[relation.start() : relation.end()]
            relation_negated = (
                relation_text.strip().startswith("!=")
                or _NEGATION_PATTERN.search(relation_text) is not None
            )
            relation_qualifier = _comparison_qualifier(relation_text)
            for range_match in _MEASUREMENT_RANGE_PATTERN.finditer(segment):
                if range_match.start() == literal_span[0]:
                    anchors.add(
                        f"{field}={_measurement_range_anchor(range_match)}"
                    )
            for literal in _LITERAL_PATTERN.finditer(value_text):
                absolute_start = relation.end() + literal.start()
                is_first_literal = absolute_start == literal_span[0]
                is_parenthesized_hex_alias = (
                    not is_first_literal
                    and _HEX_LITERAL_PATTERN.fullmatch(literal.group(0))
                    is not None
                    and re.fullmatch(
                        r"\s*\(\s*",
                        value_text[literal_span[1] - relation.end() : literal.start()],
                    )
                    is not None
                )
                if not is_first_literal and not is_parenthesized_hex_alias:
                    continue
                value = _canonical_state_value(literal.group(0)) or _normalize(
                    literal.group(0)
                ).replace(" ", "")
                qualifier = _comparison_qualifier(value_text[: literal.start()])
                qualifier = qualifier or relation_qualifier
                if qualifier is not None:
                    value = f"{qualifier}:{value}"
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


def _has_unsupported_contracted_field_negation(text: str) -> bool:
    """Reject unparsed contracted field negation rather than guessing.

    Ordinary prose contractions are handled by the bounded polarity guard.
    This separate check only applies when an explicit identifier is followed by
    a contracted negation and a v1 literal/state, where silently treating the
    relation as positive would create a false formal citation.
    """
    identifiers = list(_EXPLICIT_IDENTIFIER_PATTERN.finditer(text))
    for index, identifier_match in enumerate(identifiers):
        segment_end = (
            identifiers[index + 1].start()
            if index + 1 < len(identifiers)
            else len(text)
        )
        segment = text[identifier_match.end() : segment_end]
        for contraction in _CONTRACTED_NEGATION_PATTERN.finditer(segment):
            suffix = segment[contraction.end() :]
            if _LITERAL_PATTERN.search(suffix) or _STATE_VALUE_PATTERN.search(
                suffix
            ):
                return True
    return False


def _first_v1_literal_span(text: str) -> Optional[Tuple[int, int]]:
    spans = _literal_spans(text)
    return spans[0] if spans else None


def _literal_spans(text: str) -> Tuple[Tuple[int, int], ...]:
    spans = set()
    number_unit_spans = {
        (match.start(), match.end())
        for match in _NUMBER_UNIT_PATTERN.finditer(text)
    }
    spans.update(number_unit_spans)
    spans.update(
        (match.start(), match.end())
        for match in _HEX_LITERAL_PATTERN.finditer(text)
    )
    spans.update(
        (match.start(), match.end())
        for match in _STATE_VALUE_PATTERN.finditer(text)
    )
    spans.update(
        (match.start("lower"), match.end("lower"))
        for match in _MEASUREMENT_RANGE_PATTERN.finditer(text)
    )
    spans.update(
        (match.start("upper"), match.end("upper"))
        for match in _MEASUREMENT_RANGE_PATTERN.finditer(text)
    )
    unitless_anchors = _unitless_numeric_anchors(text)
    spans.update(
        match.span("number")
        for match in _STANDALONE_NUMBER_PATTERN.finditer(text)
        if (
            _normalize(match.group("number")) in unitless_anchors
            and _NUMBER_UNIT_PATTERN.match(text, match.start()) is None
        )
    )
    for match in _LITERAL_PATTERN.finditer(text):
        value = match.group(0)
        if not re.fullmatch(_MEASUREMENT_NUMBER_PATTERN, value):
            spans.add(match.span())
        elif _FIELD_RELATION_PATTERN.search(text[: match.start()]):
            spans.add(match.span())
    ordered = sorted(
        spans,
        key=lambda span: (span[0], -(span[1] - span[0])),
    )
    coalesced = []
    for span in ordered:
        if any(
            existing[0] <= span[0] and span[1] <= existing[1]
            for existing in coalesced
        ):
            continue
        coalesced.append(span)
    return tuple(sorted(coalesced))


def _has_unbound_literal_after(
    segment: str,
    first_span: Tuple[int, int],
) -> bool:
    previous_end = first_span[1]
    range_anchors = _measurement_range_anchors(segment)
    for span in _literal_spans(segment):
        if span[0] <= first_span[0]:
            continue
        between = segment[previous_end : span[0]]
        value = segment[span[0] : span[1]]
        if (
            _HEX_LITERAL_PATTERN.fullmatch(value) is not None
            and re.fullmatch(r"\s*\(\s*", between) is not None
        ):
            previous_end = span[1]
            continue
        if range_anchors and re.fullmatch(
            r"\s*(?:to|through|至|到|~|～|[-–—])\s*",
            between,
            re.IGNORECASE,
        ):
            previous_end = span[1]
            continue
        return True
    return False


def _has_local_identifier_literal_binding(
    identifier: str,
    segment: str,
    literal_span: Tuple[int, int],
) -> bool:
    normalized_identifier = _normalize(identifier)
    field_anchors = _field_value_anchors(f"{identifier}{segment}")
    if any(
        anchor.startswith(f"{normalized_identifier}=")
        for anchor in field_anchors
    ):
        return True

    literal_start, _ = literal_span
    unitless_anchors = _unitless_numeric_anchors(segment)
    for number_match in _STANDALONE_NUMBER_PATTERN.finditer(segment):
        if (
            number_match.start() != literal_start
            or _normalize(number_match.group("number"))
            not in unitless_anchors
        ):
            continue
        prefix = segment[: number_match.start()]
        suffix = segment[number_match.end() :]
        has_quantity_after = (
            _QUANTITY_NOUN_AFTER_NUMBER_PATTERN.match(suffix) is not None
            or _CHINESE_QUANTITY_AFTER_NUMBER_PATTERN.match(suffix)
            is not None
        )
        return has_quantity_after and (
            (
                relation := _IDENTIFIER_QUANTITY_RELATION_PATTERN.search(prefix)
            )
            is not None
            and not prefix[: relation.start()].strip()
        )
    return False


def _has_unbound_identifier_literal_claim(text: str) -> bool:
    """Reject explicit identifier claims whose first literal has no v1 binding."""
    explicit_identifiers = {
        _normalize(match.group(0))
        for match in _EXPLICIT_IDENTIFIER_PATTERN.finditer(text)
        if (
            _normalize(match.group(0)) not in _STOP_WORDS
            and _normalize(match.group(0)) not in _GENERIC_TERMS
            and _normalize(match.group(0)) not in _UNIT_TERMS
            and _normalize(match.group(0)) not in _CLOSED_STATE_VALUES
        )
    }
    if explicit_identifiers:
        for clause in re.split(r"[;!?；。！？\n]+", text):
            if _explicit_identifier_tokens(clause) & explicit_identifiers:
                continue
            if (
                _first_v1_literal_span(clause) is None
                and _LITERAL_PATTERN.search(clause) is None
            ):
                continue
            if _sections(clause) or _generation_anchors(clause):
                continue
            return True

    for clause in re.split(r"[;!?；。！？\n]+", text):
        identifier_matches = [
            match
            for match in _EXPLICIT_IDENTIFIER_PATTERN.finditer(clause)
            if (
                _normalize(match.group(0)) not in _STOP_WORDS
                and _normalize(match.group(0)) not in _GENERIC_TERMS
                and _normalize(match.group(0)) not in _UNIT_TERMS
                and _normalize(match.group(0)) not in _CLOSED_STATE_VALUES
            )
        ]
        if identifier_matches:
            if (
                _first_v1_literal_span(
                    clause[: identifier_matches[0].start()]
                )
                is not None
            ):
                return True
            normalized_identifiers = [
                _normalize(match.group(0)) for match in identifier_matches
            ]
            if len(set(normalized_identifiers)) != len(normalized_identifiers):
                return True
        for index, identifier_match in enumerate(identifier_matches):
            segment_end = (
                identifier_matches[index + 1].start()
                if index + 1 < len(identifier_matches)
                else len(clause)
            )
            segment = clause[identifier_match.end() : segment_end]
            literal_span = _first_v1_literal_span(segment)
            if literal_span is None:
                if not segment.strip():
                    if _is_terminal_state_value_identifier(
                        clause,
                        identifier_match,
                    ):
                        continue
                    return True
                topic_anchors = _topic_state_anchors(
                    f"{identifier_match.group(0)}{segment}"
                )
                if any(
                    anchor.startswith(
                        f"{_normalize(identifier_match.group(0))}=topic:"
                    )
                    for anchor in topic_anchors
                ):
                    continue
                return True
            if not _has_local_identifier_literal_binding(
                identifier_match.group(0),
                segment,
                literal_span,
            ):
                return True
            if _has_unbound_literal_after(segment, literal_span):
                return True
    return False


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
    anchors.update(_measurement_range_anchors(answer))
    anchors.update(_measurement_value_anchors(answer))
    anchors.update(_unitless_numeric_anchors(answer))
    anchors.update(_prose_negation_anchors(answer))
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


def _required_material_anchors(question: str, answer: str) -> FrozenSet[str]:
    anchors = set(_material_answer_anchors(question, answer))
    question_sections = _sections(question)
    answer_sections = _sections(answer)
    anchors.update(question_sections)
    if question_sections and answer_sections:
        question_terms = {
            _claim_term(term) for term in _semantic_terms(question)
        }
        answer_terms = {
            _claim_term(term) for term in _semantic_terms(answer)
        }
        anchors.update(question_terms & answer_terms)
    return frozenset(anchors)


def _material_candidate_anchors(hit: GovernedChunkRetrievalHit) -> FrozenSet[str]:
    """Return literals and provenance anchors exposed by one candidate."""
    anchors = set(_content_anchors(hit.chunk.content))
    anchors.update(_number_unit_pairs(hit.chunk.content))
    anchors.update(_measurement_range_anchors(hit.chunk.content))
    anchors.update(_measurement_value_anchors(hit.chunk.content))
    anchors.update(_unitless_numeric_anchors(hit.chunk.content))
    anchors.update(_prose_negation_anchors(hit.chunk.content))
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
    all_anchors = _required_material_anchors(question, answer)
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
    answer_field_anchors: FrozenSet[str] = frozenset(),
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
        and (
            not answer_field_anchors
            or bool(signal.support_anchors & answer_field_anchors)
        )
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
    if not _has_supported_v1_binding(answer):
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
    material_anchors = _required_material_anchors(question, answer)
    answer_field_anchors = _field_value_anchors(answer)
    signals = [
        _signal_for_candidate(question, answer, hit, rank, anchors)
        for rank, hit in enumerate(hits, start=1)
        if (
            not _prose_polarity_conflict(answer, hit.chunk.content)
            and (
                (not scope_groups and not selection_generations)
                or (
                    scope_groups
                    and any(
                        hit.chunk.source_id in source_ids
                        for source_ids in scope_groups.values()
                    )
                )
                or (
                    not scope_groups
                    and _candidate_generation(hit) in selection_generations
                )
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
        selected_signals.extend(
            _add_numeric_table_support(
                selected,
                group,
                answer_field_anchors,
            )
        )

    selected_ids = {signal.hit.chunk.chunk_id for signal in selected_signals}
    selected_hits = tuple(
        hit for hit in hits if hit.chunk.chunk_id in selected_ids
    )
    primary_hits = _choose_primary(selected_signals, selection_generations)
    return EvidenceSelection(selected_hits, primary_hits)
