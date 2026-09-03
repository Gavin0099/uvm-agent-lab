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
_NUMBER_UNIT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ps|ns|us|ms|pf|mv|v|a|ma|mhz|ghz)\b",
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
_FIELD_VALUE_PATTERN = re.compile(
    r"\b(?P<field>[A-Za-z][A-Za-z0-9_.-]*(?:_[A-Za-z0-9_.-]+)?)\b"
    r"[^.!?\n]{0,50}?"
    r"(?:=|:|is|equals|returns?|value\s*(?:is|=)?|"
    r"值\s*(?:為|是)?|回傳)\s*"
    r"(?P<value>\d+(?:\.\d+)?\s*(?:%|ps|ns|us|ms|pf|mv|v|a|ma|mhz|ghz)?|"
    r"zero|one|non[- ]zero)\b",
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
    {"%", "ps", "ns", "us", "ms", "pf", "mv", "v", "a", "ma", "mhz", "ghz"}
)


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
    )


def _field_value_anchors(text: str) -> FrozenSet[str]:
    explicit_fields = _explicit_identifier_tokens(text)
    anchors = set()
    for match in _FIELD_VALUE_PATTERN.finditer(text):
        field = _normalize(match.group("field"))
        if field not in explicit_fields:
            continue
        value = _normalize(match.group("value")).replace(" ", "")
        anchors.add(f"{field}={value}")
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
            (match.start(), generation)
            for match in pattern.finditer(answer)
        )
    occurrences.sort()
    scoped: dict[str, set[str]] = {
        generation: set() for generation in requested_generations
    }
    covered: set[str] = set()
    for index, (start, generation) in enumerate(occurrences):
        end = occurrences[index + 1][0] if index + 1 < len(occurrences) else len(answer)
        if generation not in scoped:
            continue
        segment_anchors = _material_answer_anchors(
            question,
            answer[start:end],
        )
        scoped[generation].update(segment_anchors)
        covered.update(segment_anchors)

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
    if "1" in tokens:
        tokens.add("one")
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
    selection_generations = requested_generations or _generation_anchors(answer)
    material_anchors_by_generation = _material_answer_anchors_by_generation(
        question,
        answer,
        selection_generations,
    )
    material_anchors = _material_answer_anchors(question, answer)
    signals = [
        _signal_for_candidate(question, answer, hit, rank, anchors)
        for rank, hit in enumerate(hits, start=1)
        if not selection_generations
        or _candidate_generation(hit) in selection_generations
    ]

    if selection_generations:
        groups = [
            (
                generation,
                [signal for signal in signals if signal.generation == generation],
            )
            for generation in selection_generations
        ]
        if any(not group for _generation, group in groups):
            return EvidenceSelection((), ())
    else:
        groups = [(None, signals)]

    selected_signals: List[_CandidateSignal] = []
    for generation, group in groups:
        required_anchors = (
            material_anchors_by_generation[generation]
            if generation is not None
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
