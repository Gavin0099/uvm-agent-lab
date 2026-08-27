from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gv100h.spec_qa.evaluation.final_evaluator import FinalPOC1Evaluator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_IDS = ["hub_reference", "usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"]


def _question(index: int) -> dict:
    if index == 49:
        status = "conflict"
        layer = "L4"
        category = "uncertainty_conflict"
        scope = "USB_HUB_COMMON"
        accepted_sources = ["usb20_fw", "usb32"]
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": ["EVIDENCE-49-A", "EVIDENCE-49-B"],
            "boundary_evidence_ids": [],
            "required_claims": [
                {"claim_id": "CLAIM-49-A", "assertion": "claim-a-49"},
                {"claim_id": "CLAIM-49-B", "assertion": "claim-b-49"},
            ],
            "section_anchors": ["section-49-a", "section-49-b"],
            "required_facts": ["claim-a-49", "claim-b-49"],
            "forbidden_claims": ["forbidden-49"],
            "acceptable_variants": [],
            "boundary_code": "UNRESOLVED_CONFLICT",
        }
        citation = {
            "document": True,
            "revision": True,
            "chapter": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "authority_level": True,
            "scope": True,
            "boundary_code": True,
            "mode": "competing_sources",
        }
    elif index == 50:
        status = "abstain"
        layer = "L4"
        category = "uncertainty_conflict"
        scope = "USB4_SPEC"
        accepted_sources = []
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": ["BOUNDARY-50"],
            "required_claims": [
                {
                    "claim_id": "CLAIM-50-BOUNDARY",
                    "assertion": "out-of-scope-boundary",
                }
            ],
            "section_anchors": [],
            "required_facts": [],
            "forbidden_claims": ["forbidden-50"],
            "acceptable_variants": [],
            "boundary_code": "OUT_OF_SCOPE",
        }
        citation = {
            "document": False,
            "revision": False,
            "section": False,
            "page_or_anchor": False,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": True,
            "mode": "boundary_evidence",
        }
    else:
        status = "answer"
        layer = (
            "L1"
            if index <= 13
            else "L2"
            if index <= 26
            else "L3"
            if index <= 38
            else "L4"
        )
        category = {
            "L1": "single_spec_fact",
            "L2": "engineering_interpretation",
            "L3": "cross_document",
            "L4": "uncertainty_conflict",
        }[layer]
        scope = "USB_HUB_COMMON"
        accepted_sources = [SOURCE_IDS[(index - 1) % len(SOURCE_IDS)]]
        gold = {
            "accepted_evidence_ids": [f"EVIDENCE-{index}"],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": [],
            "required_claims": [
                {"claim_id": f"CLAIM-{index}", "assertion": f"fact-{index}"}
            ],
            "section_anchors": [f"section-{index}"],
            "required_facts": [f"fact-{index}"],
            "forbidden_claims": [f"forbidden-{index}"],
            "acceptable_variants": [],
            "boundary_code": None,
        }
        citation = {
            "document": True,
            "revision": True,
            "chapter": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "authority_level": True,
            "scope": True,
            "boundary_code": False,
            "mode": "normative_source",
        }

    return {
        "question_id": f"QA-{index:03d}",
        "layer": layer,
        "priority": "P1" if layer == "L3" else "P0",
        "category": category,
        "question": f"question-{index}",
        "expected_status": status,
        "expected_scope": scope,
        "accepted_source_ids": accepted_sources,
        "required_citation_fields": citation,
        "gold": gold,
        "grading": {
            "factual_correctness": 0.40,
            "citation_correctness": 0.25,
            "source_authority": 0.15,
            "scope_control": 0.10,
            "uncertainty_behavior": 0.10,
        },
        "independently_reviewed": True,
        "usb4_negative_control": index == 50,
    }


def _manifest() -> dict:
    return {
        "schema_name": "poc1_spec_qa_acceptance_set",
        "schema_version": "1.1",
        "corpus_lock": "gv100h/spec_qa/contracts/corpus.lock.yaml",
        "corpus_receipt_path": "artifacts/evidence/test-results/corpus.json",
        "corpus_receipt_hash": "a" * 64,
        "dataset_version": "2.0.0",
        "benchmark_role": "poc1_acceptance_set",
        "generated_from_corpus": False,
        "independent_from_corpus": True,
        "independent_review_complete": True,
        "review_receipt_path": "artifacts/reviews/poc1-acceptance-review.json",
        "review_receipt_hash": "b" * 64,
        "reviewer_id": "synthetic-independent-reviewer",
        "reviewed_at": "2026-08-25T00:00:00Z",
        "total_questions": 50,
        "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
        "required_source_ids": SOURCE_IDS,
        "questions": [_question(index) for index in range(1, 51)],
    }


class SyntheticEvidenceResolver:
    def __init__(self, manifest: dict):
        self._ids = {
            evidence_id
            for question in manifest["questions"]
            for evidence_id in (
                question["gold"]["accepted_evidence_ids"]
                + question["gold"]["competing_evidence_ids"]
                + question["gold"]["boundary_evidence_ids"]
            )
        }
        # Canonical provenance for every evidence_id used across all 50
        # questions (answer/conflict/abstain alike), derived from the exact
        # citation shape a well-behaved response legitimately submits for it
        # (see _response() below). FinalPOC1Evaluator now fails closed on
        # EVERY citation it cannot verify against a canonical record --
        # normative and boundary/non-normative alike (Codex review, PR #33,
        # P1 and the fresh finding on ad0542c); without this, every case in
        # this file would be scored citation_valid=False purely because
        # this stub predates that check, not because the citations are
        # wrong. .get() is used because boundary-shaped response citations
        # (e.g. BOUNDARY-50) legitimately omit document/revision/etc., and
        # a missing key there must still resolve to a canonical record
        # whose document is None (a genuinely boundary-shaped canonical
        # record), not a KeyError.
        self._canonical_citations = {
            citation["evidence_id"]: SimpleNamespace(
                document=citation.get("document"),
                revision=citation.get("revision"),
                chapter=citation.get("chapter"),
                section=citation.get("section"),
                page_or_anchor=citation.get("page_or_anchor"),
                authority_level=citation.get("authority_level"),
            )
            for index in range(1, 51)
            for citation in _response(index)["citations"]
        }

    def get_evidence_by_id(self, evidence_id: str):
        # Returns the SAME canonical record get_canonical_citation_by_id()
        # uses, so _trusted_source_text() (final_evaluator.py) can resolve
        # its `.excerpt` for the excerpt-substring check (Codex review, PR
        # #33, fresh finding on d4f3bf7). This resolver has no separate
        # "raw untruncated content" concept -- the canonical record IS the
        # trusted text here -- which is fine: _trusted_source_text() falls
        # back to `.excerpt` when `.content` is absent.
        return self._canonical_citations.get(evidence_id)

    def get_canonical_citation_by_id(self, evidence_id: str):
        return self._canonical_citations.get(evidence_id)


class WeakEvidenceResolver:
    """A resolver that only implements get_evidence_by_id() -- it has no
    get_canonical_citation_by_id() at all, e.g. an older/incomplete
    integration wired up by a caller. FinalPOC1Evaluator must fail closed
    on every citation in this case, normative or boundary-shaped alike
    (Codex review, PR #33, fresh finding on ad0542c): qualification results
    must not depend on whether the caller happened to wire up a "full"
    resolver or a weaker one that cannot verify canonical evidence-shape.
    """

    def __init__(self, manifest: dict):
        self._ids = {
            evidence_id
            for question in manifest["questions"]
            for evidence_id in (
                question["gold"]["accepted_evidence_ids"]
                + question["gold"]["competing_evidence_ids"]
                + question["gold"]["boundary_evidence_ids"]
            )
        }

    def get_evidence_by_id(self, evidence_id: str):
        return object() if evidence_id in self._ids else None


def _response(index: int) -> dict:
    question = _question(index)
    status = question["expected_status"]
    if status == "answer":
        return {
            "status": status,
            "claims": [f"fact-{index}"],
            "claim_evidence_ids": [[f"EVIDENCE-{index}"]],
            "citations": [
                {
                    "evidence_id": f"EVIDENCE-{index}",
                    "document": "USB synthetic source",
                    "revision": "synthetic revision",
                    "chapter": "10",
                    "section": f"section-{index}",
                    "page_or_anchor": f"page-{index}",
                    "excerpt_or_evidence_id": f"EVIDENCE-{index}",
                    "authority_level": "authoritative",
                    "scope": question["expected_scope"],
                }
            ],
            "scope": question["expected_scope"],
            "boundary_code": None,
        }
    if status == "conflict":
        return {
            "status": status,
            "claims": ["claim-a-49", "claim-b-49"],
            "claim_evidence_ids": [["EVIDENCE-49-A"], ["EVIDENCE-49-B"]],
            "citations": [
                {
                    "evidence_id": evidence_id,
                    "document": "USB synthetic source",
                    # Deliberately distinct revisions (Codex review, PR #33,
                    # fresh finding on d5b82ba): a genuine UNRESOLVED_CONFLICT
                    # requires >=2 distinct competing provenance identities
                    # (document, revision, authority_level). The two
                    # citations previously shared the SAME revision and
                    # authority_level, differing only in section/
                    # page_or_anchor -- which is not a real conflict under
                    # validate_conflict_provenance() and would now correctly
                    # fail FinalPOC1Evaluator._conflict_provenance_ok().
                    "revision": revision,
                    "chapter": "10",
                    "section": section,
                    "page_or_anchor": section,
                    "excerpt_or_evidence_id": evidence_id,
                    "authority_level": "authoritative",
                    "scope": question["expected_scope"],
                }
                for evidence_id, section, revision in (
                    ("EVIDENCE-49-A", "section-49-a", "synthetic revision A"),
                    ("EVIDENCE-49-B", "section-49-b", "synthetic revision B"),
                )
            ],
            "scope": question["expected_scope"],
            "boundary_code": "UNRESOLVED_CONFLICT",
        }
    return {
        "status": status,
        "claims": ["out-of-scope-boundary"],
        "claim_evidence_ids": [["BOUNDARY-50"]],
        "citations": [
            {
                "evidence_id": "BOUNDARY-50",
                "excerpt_or_evidence_id": "BOUNDARY-50",
                "scope": question["expected_scope"],
            }
        ],
        "scope": question["expected_scope"],
        "boundary_code": "OUT_OF_SCOPE",
    }


def _write_manifest(tmp_path: Path) -> tuple[dict, Path]:
    manifest = _manifest()
    path = tmp_path / "poc1-acceptance-set.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, path


def test_final_evaluator_scores_structured_oracles(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    result = evaluator.run_benchmark(
        lambda query, _scope: _response(int(query.split("-")[-1]))
    )

    assert result.total_questions == 50
    assert result.answer_question_count == 48
    assert result.conflict_question_count == 1
    assert result.abstain_question_count == 1
    assert result.retrieval_recall_at_1 == 100.0
    assert result.grounded_answer_rate == 100.0
    assert result.citation_validity_rate == 100.0
    assert result.citation_completeness_rate == 100.0
    assert result.conflict_detection_rate == 100.0
    assert result.abstention_rate == 100.0
    assert result.fabricated_citations_count == 0
    assert result.authority_violations_count == 0
    assert result.all_gates_passed is True
    assert len(result.acceptance_set_hash) == 64
    assert result.dataset_hash == result.acceptance_set_hash
    assert result.review_receipt_path == "artifacts/reviews/poc1-acceptance-review.json"
    assert result.admissible_for_model_qualification is False


def test_final_evaluator_rejects_scope_mismatch_and_invalid_status(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    wrong_scope = _response(1)
    wrong_scope["scope"] = "USB4_SPEC"
    wrong_scope_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        wrong_scope,
    )
    assert wrong_scope_result.passed is False
    assert wrong_scope_result.scope_correct is False
    assert wrong_scope_result.grounded is False

    invalid_status = _response(1)
    invalid_status["status"] = "unknown"
    invalid_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        invalid_status,
    )
    assert invalid_result.passed is False
    assert invalid_result.observed_status == "invalid"
    assert invalid_result.authority_violation is True


def test_final_evaluator_rejects_normative_fields_on_abstain(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )
    response = _response(50)
    response["citations"][0]["document"] = "USB4 document not in corpus"

    result = evaluator.evaluate_response(
        evaluator.manifest.questions[49],
        response,
    )

    assert result.passed is False
    assert result.citation_complete is False


def test_final_evaluator_rejects_unknown_evidence_and_wrong_status(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    unknown = _response(1)
    unknown["citations"][0]["evidence_id"] = "UNKNOWN-EVIDENCE"
    unknown_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        unknown,
    )
    assert unknown_result.passed is False
    assert unknown_result.fabricated_citation is True
    assert unknown_result.authority_violation is True

    wrong_status = _response(50)
    wrong_status["status"] = "answer"
    wrong_result = evaluator.evaluate_response(
        evaluator.manifest.questions[49],
        wrong_status,
    )
    assert wrong_result.passed is False
    assert wrong_result.observed_status == "answer"
    assert wrong_result.grounded is False


def test_final_evaluator_rejects_boundary_citation_for_canonically_normative_evidence(
    tmp_path: Path,
):
    # Codex review, PR #33, fresh finding on ad0542c: an acceptance
    # manifest can mistakenly list an ordinary normative evidence_id under
    # boundary_evidence_ids. BOUNDARY-50 is nominally boundary evidence in
    # this manifest, but its canonical record is (mis)registered as
    # normative; the response still submits the legitimate boundary
    # citation shape (no document/revision/etc.) for it. Without canonical
    # evidence-shape verification, this would be scored fully valid because
    # the ID resolves, is in the expected set, and the missing normative
    # fields satisfy boundary-shape completeness.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["BOUNDARY-50"] = SimpleNamespace(
        document="USB4 spec, mislabeled as boundary evidence",
        revision="1.0",
        chapter="1",
        section="1.1",
        page_or_anchor="p1",
        authority_level="authoritative",
    )
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    result = evaluator.evaluate_response(evaluator.manifest.questions[49], _response(50))

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_rejects_normative_citation_for_canonically_boundary_evidence(
    tmp_path: Path,
):
    # Reverse shape mismatch (Codex review, PR #33, fresh finding on
    # ad0542c): EVIDENCE-1's canonical record is actually boundary-shaped
    # (document is None), but the response submits a fully normative-
    # looking citation for it. Canonical evidence-shape verification must
    # reject this symmetrically, not just the boundary-posing-as-normative
    # direction.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"] = SimpleNamespace(
        document=None,
        revision=None,
        chapter=None,
        section=None,
        page_or_anchor=None,
        authority_level=None,
    )
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], _response(1))

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_fails_closed_when_resolver_lacks_canonical_lookup(tmp_path: Path):
    # Codex review, PR #33, fresh finding on ad0542c: a resolver that only
    # implements get_evidence_by_id() must not give boundary-shaped
    # citations a free pass just because canonical evidence-shape cannot be
    # verified -- qualification must not silently degrade based on which
    # resolver capability the caller happened to wire up.
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=WeakEvidenceResolver(manifest),
    )

    result = evaluator.evaluate_response(evaluator.manifest.questions[49], _response(50))

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_accepts_excerpt_matching_canonical_record(tmp_path: Path):
    # Codex review, PR #33, fresh finding on 88200c5: excerpt_or_evidence_id
    # must be checked against the resolver's canonical excerpt, not just
    # checked for non-blank presence at the completeness layer. A response
    # that reports the real canonical excerpt text (not merely falling
    # back to its own evidence_id) must still pass.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].excerpt = "the real canonical excerpt text"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = "the real canonical excerpt text"

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is True
    assert result.passed is True


def test_final_evaluator_accepts_evidence_id_fallback_excerpt(tmp_path: Path):
    # The evidence_id fallback (QAResponse.to_final_qa_response()'s
    # `citation.excerpt or citation.evidence_id`) must remain valid even
    # when the canonical record separately carries a different excerpt --
    # this is a deliberate second accepted value, not the only one.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].excerpt = "a different canonical excerpt"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = "EVIDENCE-1"

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is True
    assert result.passed is True


def test_final_evaluator_rejects_fabricated_excerpt_for_normative_citation(tmp_path: Path):
    # Codex review, PR #33, fresh finding on 88200c5: a response can submit
    # a real, correctly-provenanced evidence_id but a fabricated excerpt/
    # quote and previously still pass citation_valid/citation_complete,
    # letting unsupported evidence text through the P0 grounding gate.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].excerpt = "the real canonical excerpt text"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = "a completely fabricated quote"

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_rejects_fabricated_excerpt_for_boundary_citation(tmp_path: Path):
    # Boundary citations get the same excerpt/evidence_id identity check --
    # a fabricated excerpt is a grounding problem regardless of citation
    # shape, not just for normative citations.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["BOUNDARY-50"].excerpt = "the real boundary canonical excerpt"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(50)
    response["citations"][0]["excerpt_or_evidence_id"] = "a fabricated boundary quote"

    result = evaluator.evaluate_response(evaluator.manifest.questions[49], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_accepts_genuine_substring_of_untruncated_trusted_source(tmp_path: Path):
    # Codex review, PR #33, fresh finding: excerpt verification must resolve
    # against the resolver's UNTRUNCATED trusted source text (`.content`
    # when present), not just an exact-equality comparison against whatever
    # shorter `.excerpt` string happens to be stored. A response quoting a
    # genuine, shorter verbatim substring of the full source passes even
    # though it differs from the (deliberately truncated) canonical
    # `.excerpt` field.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].content = (
        "Section 10.16.2.1 states: the real canonical excerpt text, "
        "followed by additional untruncated context that is not part of "
        "any single stored excerpt."
    )
    resolver._canonical_citations["EVIDENCE-1"].excerpt = "the real canonical excerpt text (truncated)"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = "the real canonical excerpt text"

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is True
    assert result.passed is True


def test_final_evaluator_rejects_trusted_text_contained_within_fabricated_excerpt(tmp_path: Path):
    # The substring check must only accept the submitted excerpt as a
    # substring OF the trusted source -- not the reverse. A submitted
    # excerpt that merely contains the genuine trusted text padded with
    # extra fabricated content must still be rejected as unverifiable.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].content = "the real canonical excerpt text"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = (
        "the real canonical excerpt text, plus a fabricated addendum "
        "that was never in the trusted source"
    )

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_rejects_version_conflict_with_same_canonical_revision(tmp_path: Path):
    # Codex review, PR #33, fresh finding on d5b82ba: "the front door
    # (GroundedAnswer) has a guard, the back door (FinalPOC1Evaluator's
    # benchmark agent_fn path) doesn't." A declared VERSION_CONFLICT whose
    # two citations resolve to the SAME canonical revision is not a real
    # version conflict -- it must be rejected even though every cited
    # evidence_id is individually valid, resolvable, and canonically
    # consistent (this is a CROSS-citation check, not a per-citation one).
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-49-A"].revision = "same-revision"
    resolver._canonical_citations["EVIDENCE-49-B"].revision = "same-revision"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    for citation in response["citations"]:
        citation["revision"] = "same-revision"
    response["boundary_code"] = "VERSION_CONFLICT"

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_accepts_version_conflict_with_distinct_canonical_revisions(tmp_path: Path):
    # Positive control: a VERSION_CONFLICT whose two citations resolve to
    # genuinely distinct canonical revisions (1.0 vs 1.1) is a real version
    # conflict and must pass citation_valid.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-49-A"].revision = "1.0"
    resolver._canonical_citations["EVIDENCE-49-B"].revision = "1.1"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    response["citations"][0]["revision"] = "1.0"
    response["citations"][1]["revision"] = "1.1"
    response["boundary_code"] = "VERSION_CONFLICT"

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.citation_valid is True


def test_final_evaluator_rejects_authority_mismatch_with_same_canonical_authority_level(tmp_path: Path):
    # Same gap, other half: an AUTHORITY_MISMATCH whose two citations
    # resolve to the SAME canonical authority_level is not a real
    # authority mismatch.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-49-A"].authority_level = "authoritative"
    resolver._canonical_citations["EVIDENCE-49-B"].authority_level = "authoritative"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    for citation in response["citations"]:
        citation["authority_level"] = "authoritative"
    response["boundary_code"] = "AUTHORITY_MISMATCH"

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_accepts_authority_mismatch_with_distinct_canonical_authority_levels(tmp_path: Path):
    # Positive control: authoritative vs informative is a real authority
    # mismatch and must pass citation_valid.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-49-A"].authority_level = "authoritative"
    resolver._canonical_citations["EVIDENCE-49-B"].authority_level = "informative"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    response["citations"][0]["authority_level"] = "authoritative"
    response["citations"][1]["authority_level"] = "informative"
    response["boundary_code"] = "AUTHORITY_MISMATCH"

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.citation_valid is True


def test_final_evaluator_rejects_unresolved_conflict_with_identical_canonical_provenance(tmp_path: Path):
    # UNRESOLVED_CONFLICT's own requirement: >=2 distinct provenance
    # identities (document, revision, authority_level) -- two citations
    # that resolve to an IDENTICAL canonical identity (same document, same
    # revision, same authority_level; differing only in section/
    # page_or_anchor) are the same source cited twice, not a genuine
    # conflict, even though the declared boundary_code names no specific
    # dimension.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-49-A"].revision = "identical-revision"
    resolver._canonical_citations["EVIDENCE-49-B"].revision = "identical-revision"
    resolver._canonical_citations["EVIDENCE-49-A"].authority_level = "authoritative"
    resolver._canonical_citations["EVIDENCE-49-B"].authority_level = "authoritative"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    for citation in response["citations"]:
        citation["revision"] = "identical-revision"
        citation["authority_level"] = "authoritative"
    response["boundary_code"] = "UNRESOLVED_CONFLICT"

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.citation_valid is False
    assert result.passed is False


def test_final_evaluator_non_conflict_response_skips_conflict_provenance_check(tmp_path: Path):
    # _conflict_provenance_ok() must be a no-op for non-conflict responses
    # -- an ordinary "answer" response has no competing citations to
    # validate distinctness across, and must not be penalized by a check
    # that only makes sense for status=="conflict".
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], _response(1))

    assert result.citation_valid is True


def test_final_evaluator_rejects_conflict_with_single_claim_bound_to_both_evidence_ids(
    tmp_path: Path,
):
    # Codex review, PR #33, P1, fresh finding on e3de202: a benchmark
    # agent_fn response can pack BOTH required conflict assertions into a
    # single claim string and bind that one claim to both competing
    # evidence_ids. len(claims) == len(claim_evidence_ids) == 1 and the
    # bound ids are a subset of the citations, so the traceability
    # length/subset checks alone accept it, and _contains_expected() finds
    # both required facts in the joined claim text -- but this is not the
    # >=2 distinct competing claims a real conflict requires
    # (GroundedAnswer already enforces this; the direct FinalQAResponse
    # path must too).
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = copy.deepcopy(_response(49))
    response["claims"] = ["claim-a-49 and also claim-b-49"]
    response["claim_evidence_ids"] = [["EVIDENCE-49-A", "EVIDENCE-49-B"]]

    result = evaluator.evaluate_response(evaluator.manifest.questions[48], response)

    assert result.claim_traceability_ok is False
    assert result.grounded is False
    assert result.passed is False


def test_final_evaluator_rejects_whitespace_only_excerpt(tmp_path: Path):
    # Codex review, PR #33, P2, fresh finding on e3de202: a whitespace-only
    # excerpt_or_evidence_id (e.g. " ") is not None and is a substring of
    # virtually any trusted source text containing a space, so the old
    # containment check alone would accept it. It must be rejected before
    # ever reaching the containment test.
    manifest, path = _write_manifest(tmp_path)
    resolver = SyntheticEvidenceResolver(manifest)
    resolver._canonical_citations["EVIDENCE-1"].excerpt = "the real canonical excerpt text"
    evaluator = FinalPOC1Evaluator(str(path), evidence_resolver=resolver)

    response = _response(1)
    response["citations"][0]["excerpt_or_evidence_id"] = "   "

    result = evaluator.evaluate_response(evaluator.manifest.questions[0], response)

    assert result.citation_valid is False
    assert result.passed is False