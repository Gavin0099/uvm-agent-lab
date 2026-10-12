"""Pure, opt-in provenance check for a structured single-table answer.

Reuse the existing exact source resolver and original-corpus table graph.
Neither question IDs nor Gold, model guesses, packet order or shared metadata
establish a relationship. This checks provenance, not numerical entailment.
"""
from collections.abc import Mapping

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.source_binding.table_identity import (
    bind_table_location, resolve_exact_evidence,
)
from gv100h.spec_qa.retrieval.table_family_pack import table_families

CLAIM_CITATION_RULE = """Claim-local citation contract: cite the smallest necessary set of entries that directly establishes the claim, including every number, unit, condition, scope and qualifier. Do not add a citation merely because it is related. A partial citation already covered by another complete supporting entry is redundant and must be omitted. If joint support is necessary, keep each necessary entry distinct and establish their relationship from source evidence; otherwise abstain. Never drop a necessary qualifier to make a citation appear sufficient."""
TABLE_RELATION_RULE = """Single-table structured answer contract: when the answer declares one table identity, its claim citations must belong to that same original source table family. The identity/location claim must cite its genuine caption; data claims must cite their supporting data. Same document or revision, nearby packet positions, and similar subject matter do not establish a table family. Do not guess or combine unrelated captions and rows. If identity or relationship is missing or ambiguous, return insufficient_evidence. Multiple table identities require a different contract and are not supported by this single-table format."""


class TableProvenanceError(ValueError):
    def __init__(self, code, detail, trace=None):
        super().__init__(f"{code}: {detail}")
        self.code, self.trace = code, trace or {}


def verify_single_table_relation(claims, *, sent_evidence, trusted_chunks):
    """Validate a declared table's citation edges before payload cardinality.

    The caller binds trusted_chunks to the independent corpus receipt, in
    original extraction order. For answers without a table identity this
    function is NOT_APPLICABLE; other existing source checks remain mandatory.
    """
    if not isinstance(claims, (list, tuple)) or not claims:
        raise TableProvenanceError("TABLE_CLAIMS_INVALID", "explicit claims required")
    if any(not isinstance(c, Mapping) or not isinstance(c.get("value"), Mapping)
           or not isinstance(c.get("citation_ids"), (list, tuple))
           or not c["citation_ids"]
           or any(not isinstance(cid, str) or not cid.strip() for cid in c["citation_ids"])
           or len(c["citation_ids"]) != len(set(c["citation_ids"])) for c in claims):
        raise TableProvenanceError("TABLE_CLAIMS_INVALID", "malformed claim")
    declarations = [c for c in claims if "table" in c["value"]]
    if not declarations:
        return {"status": "NOT_APPLICABLE", "reason": "no structured table identity"}
    if len(declarations) != 1:
        raise TableProvenanceError("TABLE_RELATION_AMBIGUOUS", "one declared table identity required")
    declared = declarations[0]
    value, identity = declared["value"], declared["value"]["table"]
    if (not isinstance(identity, Mapping) or set(identity) != {"source_id", "revision", "number"}
            or any(not isinstance(v, str) or not v.strip() for v in identity.values())
            or not isinstance(value.get("section"), str) or not value["section"].strip()):
        raise TableProvenanceError("TABLE_IDENTITY_INVALID", "complete public identity and section required")
    ids = list(dict.fromkeys(cid for claim in claims for cid in claim["citation_ids"]))
    try:
        resolved = resolve_exact_evidence(ids, sent_evidence=sent_evidence, trusted_chunks=trusted_chunks)
    except ValueError as exc:
        raise TableProvenanceError("TABLE_SOURCE_UNCONFIRMED", str(exc)) from exc
    originals = tuple(c if isinstance(c, GovernedChunk) else GovernedChunk.model_validate(c)
                      for c in trusted_chunks)
    families, membership = table_families(originals)
    expected = (identity["source_id"], identity["revision"], value["section"], identity["number"])
    trace = {"declared_family": list(expected), "citation_families": {
        cid: list(membership[cid]) if cid in membership else None for cid in ids}}
    for cid in ids:
        observed = membership.get(cid)
        if observed is None:
            raise TableProvenanceError("TABLE_FAMILY_UNCONFIRMED", "citation has no unambiguous original table family", trace)
        if observed != expected:
            raise TableProvenanceError("TABLE_FAMILY_MISMATCH", "cited source table family differs from the declared identity/location", trace)
    # The existing graph keys source/revision/section/number. A document
    # collision must not silently make two different originals one family.
    documents = {c.document for c in families[expected]}
    if len(documents) != 1 or any(c.document not in documents for c in resolved.values()):
        raise TableProvenanceError("TABLE_RELATION_AMBIGUOUS", "original family spans multiple documents", trace)
    try:
        binding = bind_table_location(value, declared["citation_ids"],
            sent_evidence=sent_evidence, trusted_chunks=trusted_chunks)
    except ValueError as exc:
        raise TableProvenanceError("TABLE_CAPTION_BINDING_FAILED", str(exc), trace) from exc
    return {"status": "PASS", "method": "exact sources + original table family + explicit caption binding",
            "family": list(expected), "document": next(iter(documents)),
            "caption_binding": binding, "citation_ids": ids,
            "trace": trace, "numerical_answer_correctness": "CHECKED_SEPARATELY"}
