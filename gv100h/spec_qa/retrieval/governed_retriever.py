import json
import hashlib
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Mapping, Optional, Tuple
from pydantic import BaseModel
import yaml
from gv100h.spec_qa.contracts.retrieval_policy import RetrievalPolicy
from gv100h.spec_qa.contracts.evidence_contract import Citation, EvidenceContractError
from gv100h.spec_qa.contracts.poc1_acceptance_contract import BoundaryCode
from gv100h.spec_qa.retrieval.query_normalizer import normalize_feature_selector_query


class GovernedEvidence(BaseModel):
    evidence_id: str
    authority_level: str  # "authoritative", "informative", "derived"
    scope: str            # "USB_2_0", "USB_3_X", "USB_HUB_COMMON"
    claim_level: str      # "normative_requirement", "informative_guideline"
    section: str
    title: str
    content: str
    # Which corpus.lock.yaml source this evidence was derived from (e.g.
    # "hub_reference"). This is the provenance link the Evidence Contract
    # (evidence_contract.py) requires to build a Citation's document/revision
    # fields -- an evidence entry with no traceable source cannot be cited.
    source_id: str
    entity_type: Optional[str] = None
    selector_name: Optional[str] = None
    selector_value: Optional[int] = None


class BoundaryEvidence(BaseModel):
    """
    A registered governance/corpus fact used to back an 'abstain' status's
    *boundary* claim (docs/USB_SPEC_QA_POC1_SCOPE.md Section 5) -- e.g. "USB4
    is excluded from the Phase 1 corpus". This is a distinct concept from
    GovernedEvidence/EVIDENCE_REGISTRY: it is resolvable by the same resolver
    surface (get_boundary_evidence_by_id / to_boundary_citation) but is NEVER
    eligible as normative *answer* evidence (Codex review, PR #33, P1).
    "registered" and "answer_eligible" are deliberately different properties
    -- see _validate_evidence_registry_provenance's own "registered !=
    answer_eligible" principle for EVIDENCE_REGISTRY, which this mirrors from
    the opposite direction: a BoundaryEvidence entry is registered precisely
    *because* its underlying source is excluded/ineligible as answer
    evidence, not despite it.

    A live QAService abstain path must cite a real BoundaryEvidence entry
    registered here -- never fabricate an ad-hoc Citation(evidence_id=...) at
    the call site, since FinalPOC1Evaluator would then correctly flag it as
    an unresolvable/fabricated citation.
    """

    evidence_id: str
    boundary_code: BoundaryCode
    claim: str
    scope: str
    # Which corpus.lock.yaml source this boundary fact is derived from (e.g.
    # "usb4") -- the same provenance-traceability requirement EVIDENCE_REGISTRY
    # entries have, just pointing at an excluded/ineligible source instead of
    # an answer-eligible one.
    source_id: str
    excerpt: str


class GovernedSpecRetriever:
    """
    Table-Aware Governed Retriever for USB-IF Hub Specifications.
    Supports embedded registry verification and live knowledge repo binding.
    """

    KNOWLEDGE_REPO = "Gavin0099/usb-if-hub-spec-reference"
    KNOWLEDGE_REPO_COMMIT = "808f23c24bd8651da9cdcd63ea8669126917a379"
    DEFAULT_CORPUS_LOCK_PATH = Path(__file__).resolve().parent.parent / "contracts" / "corpus.lock.yaml"
    REQUIRED_LAYERS = ("governed_reference", "official_raw", "evaluation_only")
    REQUIRED_PHASE1_SOURCES = ("hub_reference", "usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs")
    VALID_CORPUS_STATUSES = ("manifest_only_pending_binding", "phase1_bound", "fully_bound")
    VALID_BINDING_STATUSES = ("pending", "smoke_baseline_only", "bound", "verified", "locked")
    VALID_RUNTIME_BINDING_STATUSES = ("unverified", "verified", "failed")
    VALID_AUTHORITY_ROLES = ("canonical_structured_reference", "normative_official")
    REQUIRED_PENDING_BLOCKS = ("full_phase1_qualification",)
    REQUIRED_BINDING_REQUIREMENTS = (
        "immutable_commit_or_document_revision",
        "content_sha256",
        "authority_role",
    )
    SCOPE_BINDING_FIELDS = ("included_chapters", "included_scope", "canonical_entrypoint")
    PENDING_MARKERS = ("PENDING_ACQUISITION", "NOT_BOUND")
    CONTENT_HASH_ALGORITHM = "sha256_tracked_relative_posix_path_content_bytes_v3"

    # Governed Knowledge Base Table Entries (Embedded Verified Baseline)
    EVIDENCE_REGISTRY: List[GovernedEvidence] = [
        GovernedEvidence(
            evidence_id="USB3-FEAT-PORT_POWER",
            authority_level="authoritative",
            scope="USB_3_X",
            claim_level="normative_requirement",
            section="10.16.2.1",
            title="Hub Class Feature Selectors (USB 3.x)",
            content="In USB 3.x Hub specifications, PORT_POWER feature selector value is 8 (0x0008). Used with SetPortFeature to enable VBUS power to the downstream port.",
            source_id="hub_reference",
            entity_type="feature_selector",
            selector_name="PORT_POWER",
            selector_value=8,
        ),
        GovernedEvidence(
            evidence_id="USB2-FEAT-PORT_POWER",
            authority_level="authoritative",
            scope="USB_2_0",
            claim_level="normative_requirement",
            section="11.24.2.1",
            title="Hub Class Feature Selectors (USB 2.0)",
            content="In USB 2.0 Hub specifications, PORT_POWER feature selector value is 8 (0x0008).",
            source_id="hub_reference",
            entity_type="feature_selector",
            selector_name="PORT_POWER",
            selector_value=8,
        ),
        GovernedEvidence(
            evidence_id="USB3-FEAT-PORT_LINK_STATE",
            authority_level="authoritative",
            scope="USB_3_X",
            claim_level="normative_requirement",
            section="10.16.2.2",
            title="Port Link State Feature Selector (USB 3.x)",
            content="PORT_LINK_STATE feature selector value is 5 (0x0005) in USB 3.x. Not applicable to USB 2.0 (USB 3.x 專屬，在 USB 2.0 架構下無效，不支援且不適用).",
            source_id="hub_reference",
            entity_type="feature_selector",
            selector_name="PORT_LINK_STATE",
            selector_value=5,
        ),
        GovernedEvidence(
            evidence_id="USB3-HUB-DESC-FORMAT",
            authority_level="authoritative",
            scope="USB_3_X",
            claim_level="normative_requirement",
            section="10.15.2.1",
            title="USB 3.x SuperSpeed Hub Descriptor",
            content="bDescriptorType is 0x2A for SuperSpeed Hub Descriptor (USB 3.x), distinguishing it from USB 2.0 Hub Descriptor (0x29). USB 3.x Hub 不能直接使用 0x29.",
            source_id="hub_reference",
        ),
        GovernedEvidence(
            evidence_id="USB2-HUB-DESC-FORMAT",
            authority_level="authoritative",
            scope="USB_2_0",
            claim_level="normative_requirement",
            section="11.23.2.1",
            title="USB 2.0 Hub Descriptor",
            content="bDescriptorType is 0x29 for USB 2.0 Hub Descriptor. 收到 0x2A 在 USB 2.0 為未定義錯誤。",
            source_id="hub_reference",
        )
    ]

    # First-class Boundary Evidence Registry (Codex review, PR #33, P1).
    # Seeded only with boundary facts already proven by governed metadata --
    # never an invented/ad-hoc ID. USB4's Phase 1 exclusion is already a
    # declared fact in corpus.lock.yaml (sources.usb4: phase=phase_2,
    # included=false, retrieval_status=excluded_from_phase_1); this registry
    # entry just makes that fact resolvable as a citation.
    #
    # Deliberately NOT seeded here: a MISSING_EVIDENCE boundary fact. "No
    # eligible evidence was found" is a runtime retrieval observation (a
    # given query + scope + retrieval policy + corpus revision produced zero
    # results), not a static corpus/governance fact -- it cannot be
    # represented as a fixed BoundaryEvidence entry without misrepresenting a
    # runtime observation as a corpus fact. Representing it correctly needs a
    # runtime retrieval-boundary receipt (query/scope/policy/corpus_lock_hash/
    # result_count=0), which is out of scope for this registry and is tracked
    # as a follow-up rather than faked here.
    BOUNDARY_EVIDENCE_REGISTRY: List[BoundaryEvidence] = [
        BoundaryEvidence(
            evidence_id="POC1-BOUNDARY-USB4-EXCLUDED",
            boundary_code="OUT_OF_SCOPE",
            claim=(
                "USB4 is excluded from the Phase 1 corpus (corpus.lock.yaml "
                "sources.usb4: phase=phase_2, included=false, "
                "retrieval_status=excluded_from_phase_1)."
            ),
            scope="USB4_SPEC",
            source_id="usb4",
            excerpt=(
                "corpus.lock.yaml sources.usb4: phase=phase_2, included=false, "
                "retrieval_status=excluded_from_phase_1."
            ),
        ),
    ]

    def __init__(
        self,
        knowledge_repo_path: Optional[str] = None,
        corpus_lock_path: Optional[str] = None,
        require_physical_binding: bool = False,
        source_paths: Optional[Mapping[str, str | Path]] = None,
    ):
        self.corpus_lock_path = (
            Path(corpus_lock_path).resolve()
            if corpus_lock_path
            else self.DEFAULT_CORPUS_LOCK_PATH
        )
        self.corpus_lock = self._load_corpus_lock(self.corpus_lock_path)
        self.corpus_lock_validation = self.validate_corpus_lock(self.corpus_lock)
        self._validate_evidence_registry_provenance(self.corpus_lock)
        self._validate_boundary_evidence_registry_provenance(self.corpus_lock)
        self.require_physical_binding = require_physical_binding
        self.lock_binding_status = self.corpus_lock["status"]
        self.runtime_binding_status = "unverified"
        self.physical_binding_verified = False
        self.qualification_blocked = False
        self.qualification_block_reasons = ()
        self.runtime_bindings = {
            source_id: {
                "status": "unverified",
                "observed_path": None,
                "observed_sha256": None,
                "observed_commit": None,
            }
            for source_id in self.REQUIRED_PHASE1_SOURCES
        }
        governed_source = self.corpus_lock["sources"]["hub_reference"]
        self.knowledge_repo = governed_source["repo"]
        self.knowledge_repo_commit = governed_source["commit"]
        self.corpus_id = self.corpus_lock["corpus_id"]
        self.corpus_binding_status = self.corpus_lock["status"]
        self.binding_mode = f"embedded_registry_baseline ({self.corpus_binding_status})"
        self.bound_repo_head_commit = None
        self.bound_repo_files_hash = None

        requested_paths = dict(source_paths or {})
        if knowledge_repo_path:
            if "hub_reference" in requested_paths and Path(requested_paths["hub_reference"]).resolve() != Path(knowledge_repo_path).resolve():
                raise ValueError("knowledge_repo_path conflicts with source_paths.hub_reference")
            requested_paths["hub_reference"] = knowledge_repo_path
        unknown_sources = set(requested_paths) - set(self.REQUIRED_PHASE1_SOURCES)
        if unknown_sources:
            raise ValueError(
                "source_paths contains unknown Phase 1 source IDs: "
                + ", ".join(sorted(unknown_sources))
            )

        try:
            for source_id, source_path in requested_paths.items():
                self._verify_physical_source(source_id, source_path)
        except Exception:
            self.runtime_binding_status = "failed"
            self._refresh_qualification_state()
            raise

        missing_sources = [
            source_id
            for source_id in self.REQUIRED_PHASE1_SOURCES
            if source_id not in requested_paths
        ]
        if require_physical_binding and missing_sources:
            self.runtime_binding_status = "failed"
            self._refresh_qualification_state()
            raise ValueError(
                "physical corpus binding requires paths for: "
                + ", ".join(missing_sources)
            )

        self._refresh_qualification_state()

    def _validate_evidence_registry_provenance(self, corpus_lock: Mapping[str, Any]) -> None:
        """
        Every EVIDENCE_REGISTRY entry must declare a source_id that is a known
        key in corpus.lock.yaml's sources table. An evidence entry with an
        unregistered source_id cannot be traced back to a document/revision,
        so it can never be resolved into a Citation -- fail closed at load
        time rather than at citation-build time.
        """
        known_source_ids = set(corpus_lock["sources"])
        unknown = [
            ev.evidence_id
            for ev in self.EVIDENCE_REGISTRY
            if ev.source_id not in known_source_ids
        ]
        if unknown:
            raise ValueError(
                "EVIDENCE_REGISTRY contains entries with unregistered source_id "
                "(not present in corpus.lock.yaml sources): "
                + ", ".join(unknown)
            )

        # Being a *known* source_id is not the same as being *eligible as
        # answer evidence*: corpus.lock.yaml deliberately registers excluded
        # sources too (e.g. "usb4", phase_2/included=false) so their
        # exclusion is itself traceable. Without this check, an
        # EVIDENCE_REGISTRY entry could reference such a source and both
        # query() and to_citation() would happily surface it as ordinary
        # answer evidence -- letting an explicit negative-control source
        # leak into answers (Codex review, PR #33, P1). A source is eligible
        # only when it is bound to the current phase, not excluded, and its
        # declared layer is itself marked allowed_as_answer_evidence in
        # corpus.lock.yaml.
        layers = corpus_lock.get("layers", {})
        ineligible = []
        for ev in self.EVIDENCE_REGISTRY:
            source = corpus_lock["sources"].get(ev.source_id, {})
            layer = layers.get(source.get("layer"), {})
            is_eligible = (
                source.get("phase") == "phase_1"
                and source.get("included", True) is not False
                and layer.get("allowed_as_answer_evidence") is True
            )
            if not is_eligible:
                ineligible.append(f"{ev.evidence_id!r} (source_id={ev.source_id!r})")
        if ineligible:
            raise ValueError(
                "EVIDENCE_REGISTRY contains entries whose source is not "
                "eligible as answer evidence (must be phase_1, not excluded, "
                "and declared on a layer with allowed_as_answer_evidence=true "
                "in corpus.lock.yaml): " + ", ".join(ineligible)
            )

    def _validate_boundary_evidence_registry_provenance(self, corpus_lock: Mapping[str, Any]) -> None:
        """
        Every BOUNDARY_EVIDENCE_REGISTRY entry must declare a source_id that
        is a known key in corpus.lock.yaml's sources table (the same
        traceability requirement EVIDENCE_REGISTRY has), and entries must
        have unique evidence_id values that never collide with
        EVIDENCE_REGISTRY's own evidence_ids -- a resolver caller must always
        be able to tell, from the ID alone, which registry (and therefore
        which eligibility) a resolved evidence entry belongs to.
        """
        known_source_ids = set(corpus_lock["sources"])
        unknown = [
            be.evidence_id
            for be in self.BOUNDARY_EVIDENCE_REGISTRY
            if be.source_id not in known_source_ids
        ]
        if unknown:
            raise ValueError(
                "BOUNDARY_EVIDENCE_REGISTRY contains entries with unregistered "
                "source_id (not present in corpus.lock.yaml sources): "
                + ", ".join(unknown)
            )

        boundary_ids = [be.evidence_id for be in self.BOUNDARY_EVIDENCE_REGISTRY]
        if len(boundary_ids) != len(set(boundary_ids)):
            raise ValueError("BOUNDARY_EVIDENCE_REGISTRY contains duplicate evidence_id values")

        answer_evidence_ids = {ev.evidence_id for ev in self.EVIDENCE_REGISTRY}
        colliding = sorted(answer_evidence_ids.intersection(boundary_ids))
        if colliding:
            raise ValueError(
                "BOUNDARY_EVIDENCE_REGISTRY evidence_id values must not collide "
                "with EVIDENCE_REGISTRY evidence_id values: " + ", ".join(colliding)
            )

    def to_citation(self, ev: GovernedEvidence, *, excerpt_max_len: int = 240) -> Citation:
        """
        Resolve a GovernedEvidence into a Citation per the Evidence Contract
        (evidence_contract.py), using corpus.lock.yaml as the source of truth
        for document/revision provenance.

        corpus.lock.yaml sources come in two shapes:
        - official_raw sources (usb20_fw, usb20_se, usb32,
          superspeed_hub_lvs) declare document + revision directly.
        - the hub_reference governed_reference source instead declares
          repo + commit (no document/revision keys), so those are used as
          the document/revision fallback.

        `chapter` is derived from the evidence's own `section` field (e.g.
        "10.16.2.1" -> chapter "10"), which is consistent with corpus.lock.yaml's
        declared `included_chapters` per source (e.g. hub_reference-derived
        sections such as "10.16.2.1"/"11.24.2.1" fall inside the USB 3.2
        chapter-10 / USB 2.0 chapter-11 ranges already recorded there).
        """
        source = self.corpus_lock["sources"].get(ev.source_id)
        if source is None:
            raise EvidenceContractError(
                f"evidence {ev.evidence_id!r} declares unregistered source_id "
                f"{ev.source_id!r}; cannot resolve document/revision"
            )

        document = source.get("document", source.get("repo", ev.source_id))
        revision = source.get("revision", source.get("commit", "unknown"))
        chapter = self._derive_chapter(ev)

        excerpt = ev.content
        if excerpt_max_len and len(excerpt) > excerpt_max_len:
            excerpt = excerpt[: excerpt_max_len - 1].rstrip() + "\u2026"

        return Citation(
            evidence_id=ev.evidence_id,
            document=document,
            revision=revision,
            chapter=chapter,
            section=ev.section,
            page_or_anchor=ev.section,
            authority_level=ev.authority_level,
            excerpt=excerpt,
        )

    @staticmethod
    def _derive_chapter(ev: GovernedEvidence) -> str:
        chapter = ev.section.split(".")[0].strip()
        if not chapter or not chapter.isdigit():
            raise EvidenceContractError(
                f"evidence {ev.evidence_id!r} has a section {ev.section!r} that "
                "does not start with a numeric chapter segment; cannot derive "
                "a citation chapter"
            )
        return chapter


    def _refresh_qualification_state(self) -> None:
        block_reasons = list(self.corpus_lock_validation["block_reasons"])
        unverified_sources = [
            source_id
            for source_id, binding in self.runtime_bindings.items()
            if binding["status"] != "verified"
        ]
        self.physical_binding_verified = not unverified_sources
        if unverified_sources:
            block_reasons.extend(
                f"runtime source {source_id} physical binding is {self.runtime_bindings[source_id]['status']}"
                for source_id in unverified_sources
            )
            self.runtime_binding_status = (
                "failed"
                if any(self.runtime_bindings[source_id]["status"] == "failed" for source_id in unverified_sources)
                else "unverified"
            )
        else:
            self.runtime_binding_status = "verified"
        self.qualification_block_reasons = tuple(dict.fromkeys(block_reasons))
        self.qualification_blocked = bool(self.qualification_block_reasons)

    def _verify_physical_source(self, source_id: str, source_path: str | Path) -> None:
        try:
            if source_id == "hub_reference":
                if not Path(source_path).resolve().exists():
                    raise FileNotFoundError(
                        f"governed reference path does not exist: {source_path}"
                    )
                self.verify_and_bind_knowledge_repo(source_path)
            else:
                self._verify_document_source(source_id, source_path)
        except Exception:
            self.runtime_bindings[source_id]["status"] = "failed"
            raise

    def _verify_document_source(self, source_id: str, source_path: str | Path) -> None:
        path = Path(source_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"physical source file does not exist: {path}")

        expected_hash = self.corpus_lock["sources"][source_id]["content_sha256"]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_hash)):
            raise ValueError(f"source {source_id} content hash is not bound")
        observed_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed_hash.lower() != str(expected_hash).lower():
            raise ValueError(
                f"source {source_id} content hash does not match corpus lock: "
                f"{observed_hash} != {expected_hash}"
            )

        self.runtime_bindings[source_id] = {
            "status": "verified",
            "observed_path": str(path),
            "observed_sha256": observed_hash,
            "observed_commit": None,
        }

    @classmethod
    def validate_corpus_lock(cls, lock: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(lock, dict):
            raise ValueError("POC-1 corpus lock must contain a YAML mapping")
        if not lock.get("corpus_id") or not lock.get("status"):
            raise ValueError("POC-1 corpus lock requires corpus_id and status")
        if lock["status"] not in cls.VALID_CORPUS_STATUSES:
            raise ValueError(f"invalid corpus status: {lock['status']}")

        layers = lock.get("layers")
        missing_layers = [layer for layer in cls.REQUIRED_LAYERS if not isinstance(layers, dict) or layer not in layers]
        if missing_layers:
            raise ValueError(f"required layers missing: {', '.join(missing_layers)}")
        for layer_name in cls.REQUIRED_LAYERS:
            if not isinstance(layers[layer_name], dict):
                raise ValueError(f"layer {layer_name} must be a mapping")
            if not isinstance(layers[layer_name].get("allowed_as_answer_evidence"), bool):
                raise ValueError(f"layer {layer_name} requires boolean allowed_as_answer_evidence")
        if layers["evaluation_only"]["allowed_as_answer_evidence"] is not False:
            raise ValueError("evaluation_only layer must not be answer evidence")

        sources = lock.get("sources")
        if not isinstance(sources, dict):
            raise ValueError("POC-1 corpus lock requires sources mapping")
        missing_sources = [source_id for source_id in cls.REQUIRED_PHASE1_SOURCES if source_id not in sources]
        if missing_sources:
            raise ValueError(f"required Phase 1 source IDs missing: {', '.join(missing_sources)}")

        binding_requirements = lock.get("binding_requirements")
        if not isinstance(binding_requirements, dict):
            raise ValueError("POC-1 corpus lock requires binding_requirements mapping")
        declared_requirements = binding_requirements.get("source_entry_must_have")
        if not isinstance(declared_requirements, list) or not set(cls.REQUIRED_BINDING_REQUIREMENTS).issubset(declared_requirements):
            raise ValueError("binding_requirements.source_entry_must_have is incomplete")
        scope_binding = binding_requirements.get("scope_binding")
        declared_scope_fields = scope_binding.get("requires_one_of") if isinstance(scope_binding, dict) else None
        if not isinstance(declared_scope_fields, list) or set(declared_scope_fields) != set(cls.SCOPE_BINDING_FIELDS):
            raise ValueError("binding_requirements.scope_binding.requires_one_of is invalid")
        pending_blocks = binding_requirements.get("pending_markers_block")
        if not isinstance(pending_blocks, list) or not set(cls.REQUIRED_PENDING_BLOCKS).issubset(pending_blocks):
            raise ValueError("binding_requirements.pending_markers_block is incomplete")
        if binding_requirements.get("content_hash_algorithm") != cls.CONTENT_HASH_ALGORITHM:
            raise ValueError("binding_requirements.content_hash_algorithm is invalid")

        block_reasons = []
        for source_id in cls.REQUIRED_PHASE1_SOURCES:
            source = sources[source_id]
            if not isinstance(source, dict):
                raise ValueError(f"source {source_id} must be a mapping")
            if source.get("phase") != "phase_1":
                raise ValueError(f"source {source_id} must be phase_1")
            if source.get("layer") not in ("governed_reference", "official_raw"):
                raise ValueError(f"source {source_id} has invalid layer")
            if source.get("role") not in cls.VALID_AUTHORITY_ROLES:
                raise ValueError(f"source {source_id} has invalid authority role")
            if not (source.get("commit") or source.get("revision")):
                raise ValueError(f"source {source_id} requires immutable commit or revision")
            if not source.get("content_sha256"):
                raise ValueError(f"source {source_id} requires content_sha256")
            if source_id == "hub_reference" and source.get("binding_status") in ("bound", "verified", "locked"):
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(source["content_sha256"])):
                    raise ValueError("bound hub_reference requires a SHA-256 content hash")
                if source.get("content_hash_algorithm") != cls.CONTENT_HASH_ALGORITHM:
                    raise ValueError("hub_reference content hash algorithm does not match binding contract")
            if not any(source.get(field) for field in declared_scope_fields):
                raise ValueError(f"source {source_id} requires one of {', '.join(declared_scope_fields)}")

            binding_status = source.get("binding_status")
            if binding_status not in cls.VALID_BINDING_STATUSES:
                raise ValueError(f"source {source_id} has invalid binding_status")
            if binding_status not in ("bound", "verified", "locked"):
                block_reasons.append(f"sources.{source_id}.binding_status={binding_status}")
            for marker_path in cls._find_pending_markers(source, f"sources.{source_id}"):
                block_reasons.append(f"{marker_path} contains pending marker")

        usb4 = sources.get("usb4")
        if not isinstance(usb4, dict) or usb4.get("included") is not False:
            raise ValueError("USB4 must be excluded from Phase 1")

        benchmark = lock.get("benchmark")
        if not isinstance(benchmark, dict) or benchmark.get("benchmark_role") != "independent_evaluation":
            raise ValueError("benchmark must be independent_evaluation")
        if benchmark.get("generated_from_corpus") is not False or benchmark.get("independent_from_corpus") is not True:
            raise ValueError("benchmark independence contract is invalid")

        if lock["status"] in ("phase1_bound", "fully_bound") and block_reasons:
            raise ValueError("corpus status claims qualification while pending markers remain")
        return {
            "qualification_blocked": bool(block_reasons),
            "block_reasons": tuple(block_reasons),
        }

    @classmethod
    def _find_pending_markers(cls, value: Any, path: str) -> List[str]:
        markers = []
        if isinstance(value, dict):
            for key, child in value.items():
                markers.extend(cls._find_pending_markers(child, f"{path}.{key}"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                markers.extend(cls._find_pending_markers(child, f"{path}[{index}]"))
        elif isinstance(value, str) and value in cls.PENDING_MARKERS:
            markers.append(path)
        return markers

    @staticmethod
    def _load_corpus_lock(lock_path: Path) -> Dict[str, Any]:
        if not lock_path.exists():
            raise FileNotFoundError(f"POC-1 corpus lock not found: {lock_path}")

        with lock_path.open("r", encoding="utf-8") as handle:
            lock = yaml.safe_load(handle)

        if not isinstance(lock, dict):
            raise ValueError("POC-1 corpus lock must contain a YAML mapping")
        if not lock.get("corpus_id") or not lock.get("status"):
            raise ValueError("POC-1 corpus lock requires corpus_id and status")

        sources = lock.get("sources")
        governed_source = sources.get("hub_reference") if isinstance(sources, dict) else None
        if not isinstance(governed_source, dict) or not governed_source.get("repo"):
            raise ValueError("POC-1 corpus lock requires sources.hub_reference.repo")
        if not governed_source.get("commit"):
            raise ValueError("POC-1 corpus lock requires sources.hub_reference.commit")

        return lock

    def verify_and_bind_knowledge_repo(self, repo_path: str) -> bool:
        """
        Verifies the physical governed reference against the corpus lock.
        """
        r_path = Path(repo_path).resolve()
        if not r_path.exists():
            return False

        head_result = subprocess.run(
            ["git", "-C", str(r_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if head_result.returncode != 0 or not head_result.stdout.strip():
            raise ValueError("governed reference path is not a Git checkout")
        actual_commit = head_result.stdout.strip()
        expected_source = self.corpus_lock["sources"]["hub_reference"]
        if actual_commit != expected_source["commit"]:
            raise ValueError(
                "governed reference commit does not match corpus lock: "
                f"{actual_commit} != {expected_source['commit']}"
            )

        entrypoint = expected_source.get("canonical_entrypoint")
        if entrypoint and not (r_path / entrypoint).is_file():
            raise ValueError(f"governed reference canonical entrypoint is missing: {entrypoint}")

        content_hash, file_count = self._compute_knowledge_repo_content_hash(r_path)
        expected_hash = expected_source["content_sha256"]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_hash)):
            raise ValueError("corpus lock content hash is not bound")
        if content_hash.lower() != str(expected_hash).lower():
            raise ValueError(
                "governed reference content hash does not match corpus lock: "
                f"{content_hash} != {expected_hash}"
            )

        self.bound_repo_head_commit = actual_commit
        self.bound_repo_files_hash = content_hash
        self.runtime_bindings["hub_reference"] = {
            "status": "verified",
            "observed_path": str(r_path),
            "observed_sha256": content_hash,
            "observed_commit": actual_commit,
        }
        self.runtime_binding_status = "verified"
        self.physical_binding_verified = True
        self.binding_mode = f"live_repo_bound ({file_count} files verified)"
        self._refresh_qualification_state()
        return True

    @staticmethod
    def _compute_knowledge_repo_content_hash(repo_path: Path) -> tuple[str, int]:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("governed reference tracked file list is unavailable")

        tracked_paths = sorted(
            path.decode("utf-8")
            for path in result.stdout.split(b"\0")
            if path and Path(path.decode("utf-8")).suffix.lower() in {".md", ".yaml", ".json"}
        )
        hasher = hashlib.sha256()
        for relative_path in tracked_paths:
            hasher.update(relative_path.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update((repo_path / relative_path).read_bytes())
        return hasher.hexdigest(), len(tracked_paths)

    # Tokens that appear across most/all EVIDENCE_REGISTRY entries (or are
    # otherwise too generic within the USB Hub domain, e.g. "link" showing up
    # in unrelated Link Training / Link Power Management contexts, or
    # "downstream"/"upstream" being a structural Hub port concept used when
    # describing power, reset, and link-state topics alike -- observed
    # concretely when a Warm Reset / link-states question incidentally
    # matched USB3-FEAT-PORT_POWER purely because its content happens to
    # mention "downstream port"). A bare overlap on one of these words
    # carries no discriminative topic signal, so it must never by itself
    # justify treating an evidence entry as a relevant candidate.
    _GENERIC_TOKENS = frozenset({
        "usb", "hub", "port", "class", "spec", "specification", "specifications",
        "feature", "features", "selector", "selectors", "link", "state", "states",
        "downstream", "upstream",
        "descriptor", "descriptors", "value", "values", "chapter", "section",
        "version", "revision", "the", "and", "for", "with", "in", "of", "is",
        "are", "to", "on", "at", "not",
    })

    # Deterministic word tokenizer: alphanumeric/underscore identifiers (so
    # "port_link_state" stays one token) or runs of CJK characters. This is
    # used instead of naive `.split()` so natural-language punctuation and
    # hyphenation ("downstream-port", "power,", "feature?") don't prevent a
    # genuine word match, and so purely numeric/version-like tokens (e.g.
    # "3.2") are never fed into the generic title/content overlap check --
    # they can only ever contribute relevance through the structured
    # section-reference matcher below.
    _WORD_TOKEN_PATTERN = re.compile(r"[a-z_][a-z0-9_]*|[\u4e00-\u9fff]+")

    # A "section reference" in a query is any dotted numeric fragment (e.g.
    # "11.24.2.1", "11.23", "3.2"). It is matched against an evidence's
    # (opaque) `section` identifier by per-segment prefix comparison, not by
    # substring containment: "11.23" is a legitimate prefix of "11.23.2.1",
    # but "3.2" must NOT match "11.23.2.1" just because the digits "3.2"
    # happen to appear inside it. This generalizes cleanly to any section
    # number without hardcoding a new `if "<section>" in q_lower` rule per
    # entry as the corpus grows.
    _SECTION_REF_PATTERN = re.compile(r"\d+(?:\.\d+)+")

    @staticmethod
    def _section_ref_matches(query_section: str, ev_section: str) -> bool:
        query_parts = query_section.split(".")
        ev_parts = ev_section.split(".")
        if len(query_parts) > len(ev_parts):
            return False
        return query_parts == ev_parts[: len(query_parts)]

    def _lookup_feature_selectors(
        self,
        value: int,
        allowed_evidence_scopes: Optional[set] = None,
        answer_scope: Optional[str] = None,
    ) -> List[Tuple[int, GovernedEvidence]]:
        scored: List[Tuple[int, GovernedEvidence]] = []
        for ev in self.EVIDENCE_REGISTRY:
            if ev.entity_type != "feature_selector" or ev.selector_value != value:
                continue
            if allowed_evidence_scopes is not None and ev.scope not in allowed_evidence_scopes:
                continue
            score = 40
            if answer_scope and ev.scope == answer_scope:
                score += 5
            scored.append((score, ev))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    def query(
        self,
        query_text: str,
        retrieval_policy: Optional[RetrievalPolicy] = None,
    ) -> List[GovernedEvidence]:
        q_lower = query_text.lower()
        query_tokens = self._WORD_TOKEN_PATTERN.findall(q_lower)
        query_section_refs = self._SECTION_REF_PATTERN.findall(q_lower)
        # RetrievalPolicy.allowed_evidence_scopes is a caller-declared hard
        # eligibility boundary, not a reranking signal (unlike the old
        # `target_scope` bonus it replaces). When no policy is supplied,
        # retrieval is unscoped (as before): any evidence scope is eligible,
        # and only topic relevance decides candidacy. The retriever itself
        # never infers `allowed_evidence_scopes` from query text -- see
        # RetrievalPolicy's docstring for why.
        allowed_evidence_scopes = (
            set(retrieval_policy.allowed_evidence_scopes) if retrieval_policy else None
        )
        answer_scope = retrieval_policy.answer_scope if retrieval_policy else None
        structured = normalize_feature_selector_query(query_text, answer_scope)
        scored_by_id: Dict[str, Tuple[int, GovernedEvidence]] = {}

        def add_scored(score: int, ev: GovernedEvidence) -> None:
            prev = scored_by_id.get(ev.evidence_id)
            if prev is None or score > prev[0]:
                scored_by_id[ev.evidence_id] = (score, ev)

        if structured is not None:
            structured_hits = self._lookup_feature_selectors(
                structured["value"],
                allowed_evidence_scopes=allowed_evidence_scopes,
                answer_scope=answer_scope,
            )
            if not structured_hits:
                return []
            for score, ev in structured_hits:
                add_scored(score, ev)

        for ev in self.EVIDENCE_REGISTRY:
            if allowed_evidence_scopes is not None and ev.scope not in allowed_evidence_scopes:
                # Hard eligibility gate, applied before any topic-relevance
                # scoring: an evidence entry outside the caller-declared
                # allowed_evidence_scopes can never become a candidate here,
                # no matter how strong its topical match would otherwise be.
                continue

            # `strong_score` captures only high-precision topic signals that
            # are sufficient, on their own, to establish `ev` as a candidate:
            # explicit concept/technical-phrase aliases and structured
            # section-reference matches. `lexical_bonus` (below) captures
            # low-precision generic word overlap between the query and the
            # evidence title/content; it may only ever *rerank* an evidence
            # entry that a strong signal has already qualified as a
            # candidate -- it must never by itself create one. Without this
            # separation, any ordinary content word that happens to appear
            # in an evidence's description (e.g. "used", "enable") would be
            # enough to manufacture a false candidate, an unbounded stoplist
            # "whack-a-mole" problem (concretely observed with
            # "link"/"downstream"/"upstream" before this split existed).
            # `answer_scope` is excluded from both: it may only rerank an
            # already-established candidate (see the scope bonus below), and
            # it plays no role in the eligibility gate above beyond what
            # `allowed_evidence_scopes` already encodes.
            strong_score = 0

            if "descriptor" in q_lower or "描述符" in q_lower or "bdescriptortype" in q_lower:
                if "DESC" in ev.evidence_id:
                    strong_score += 15
            # PR #29 review regression (5th pass): "power" + a mere
            # feature-selector qualifier (e.g. "Which feature controls link
            # power management in USB 3.2?") is STILL not high-precision
            # enough -- that question is about USB 3.2 Link Power Management,
            # not the Hub Class PORT_POWER feature selector, yet it contains
            # both "power" and "feature". A bare "power" token may only be
            # treated as strong when it co-occurs with BOTH (a) explicit
            # port/VBUS context (`port`/`downstream`/`vbus`) AND (b) a
            # feature-selector qualifier (`feature`/`selector`) -- "power"
            # alone, or "power"+qualifier without port/VBUS context, is not
            # enough. All matching is on tokenized words (`query_tokens`),
            # not substrings of `q_lower`, so "powered"/"powerful" can't
            # misfire.
            #
            # PR #29 review regression (6th pass): `SetPortFeature` /
            # `ClearPortFeature` / `VBUS` were previously treated as
            # unambiguous PORT_POWER technical identifiers on their own, but
            # none of them is actually PORT_POWER-specific: `SetPortFeature`
            # and `ClearPortFeature` are generic Hub Class requests that also
            # apply to PORT_RESET and every other feature selector, and
            # `VBUS` alone is an electrical/power-delivery term, not a Hub
            # Class PORT_POWER selector question (e.g. "What is the VBUS
            # current limit in USB 3.2?"). None of the three may establish a
            # PORT_POWER candidate by itself; they remain useful only as
            # `lexical_bonus` rerank signal for a candidate already
            # established by another strong signal.
            query_token_set = set(query_tokens)
            has_explicit_port_power_phrase = (
                "port_power" in q_lower
                or "port power" in q_lower
                or "downstream port power" in q_lower
                or "vbus power" in q_lower
                or "電源" in q_lower
            )
            has_power_with_port_context_and_qualifier = (
                "power" in query_token_set
                and bool(query_token_set & {"port", "downstream", "vbus"})
                and bool(query_token_set & {"feature", "selector"})
            )
            if has_explicit_port_power_phrase or has_power_with_port_context_and_qualifier:
                if "PORT_POWER" in ev.evidence_id:
                    strong_score += 15
            has_explicit_link_state_phrase = (
                "port_link_state" in q_lower or "port link state" in q_lower
            )
            # PR #29 review regression (2nd pass): a bare "link state"
            # substring match reopened the exact Warm Reset false-positive
            # this fix set out to close -- "which link states allow a
            # downstream port to issue a Warm Reset" contains "link state"
            # as a substring of "link states" and is NOT a PORT_LINK_STATE
            # question. With only 5 embedded evidence entries, fail-closed:
            # a bare "link state"/"link states" phrase is only treated as a
            # genuine PORT_LINK_STATE alias when it co-occurs with an
            # explicit feature-selector qualifier word. A plain regex word
            # boundary (`\blink state\b`) is not sufficient either, since
            # "link state machine"/"link state transition timing" would
            # still be misidentified as a PORT_LINK_STATE feature-selector
            # question without a qualifier. This is intentionally narrow;
            # once a formal Query Normalizer layer exists, this kind of
            # concept-alias detection should move out of the retriever.
            has_bare_link_state_with_qualifier = "link state" in q_lower and any(
                qualifier in q_lower
                for qualifier in ("feature", "selector", "field", "pls", "value")
            )
            if has_explicit_link_state_phrase or has_bare_link_state_with_qualifier:
                if "PORT_LINK_STATE" in ev.evidence_id:
                    strong_score += 15

            for section_ref in query_section_refs:
                if self._section_ref_matches(section_ref, ev.section):
                    strong_score += 20

            if strong_score <= 0:
                # No high-precision topic signal was found. Generic lexical
                # overlap, scope match, or nothing at all must never qualify
                # an evidence entry as a candidate on their own: abstain
                # instead of guessing.
                continue

            # PR #29 review regression (3rd pass): with strong-signal-only
            # gating in place, low-precision generic word overlap is now
            # safe to compute as a rerank-only bonus, since it can no longer
            # by itself create a candidate for evidence with zero genuine
            # topic relevance.
            lexical_bonus = 0
            for token in query_tokens:
                if (
                    len(token) > 2
                    and token not in self._GENERIC_TOKENS
                    and (token in ev.title.lower() or token in ev.content.lower())
                ):
                    lexical_bonus += 2

            score = strong_score + lexical_bonus
            if answer_scope and ev.scope == answer_scope:
                # Rerank-only: prefer the evidence that matches the answer's
                # own scope over other evidence the eligibility gate above
                # has already allowed in (e.g. an explicit_cross_scope
                # policy that allows both USB_2_0 and USB_3_X evidence for a
                # USB_2_0 answer_scope question should still rank the
                # USB_2_0 evidence first).
                score += 5

            add_scored(score, ev)

        scored_results = list(scored_by_id.values())
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results]

    def get_evidence_by_id(
        self, evidence_id: str
    ) -> Optional[GovernedEvidence | BoundaryEvidence]:
        """
        Resolve ``evidence_id`` against BOTH the answer-eligible
        EVIDENCE_REGISTRY and the BOUNDARY_EVIDENCE_REGISTRY.

        This is the resolver an evaluator uses to ask "does this evidence_id
        correspond to a genuinely registered piece of evidence?" (fabrication
        detection) -- a *different* question from "is this evidence eligible
        to be retrieved and cited as answer support?", which remains query()'s
        exclusive concern (query() only ever searches EVIDENCE_REGISTRY).
        Conflating the two would either (a) make boundary evidence
        unresolvable, so any evaluator that only calls get_evidence_by_id
        cannot distinguish a real boundary citation (e.g. backing a USB4
        abstain) from a fabricated one, or (b) make query() return boundary
        evidence as if it could support an answer. Keeping them separate
        methods preserves: resolvable != retrievable_as_answer (Codex review,
        PR #33, P1).
        """
        for ev in self.EVIDENCE_REGISTRY:
            if ev.evidence_id == evidence_id:
                return ev
        for be in self.BOUNDARY_EVIDENCE_REGISTRY:
            if be.evidence_id == evidence_id:
                return be
        return None

    def get_boundary_evidence_by_id(self, evidence_id: str) -> Optional[BoundaryEvidence]:
        for be in self.BOUNDARY_EVIDENCE_REGISTRY:
            if be.evidence_id == evidence_id:
                return be
        return None

    def to_boundary_citation(self, be: BoundaryEvidence) -> Citation:
        """
        Resolve a registered BoundaryEvidence into a Citation for an
        'abstain' response's boundary claim -- a *boundary* citation shape
        (evidence_id + excerpt only, no normative document/revision/chapter/
        section/page_or_anchor/authority_level fields), per
        poc1_acceptance_contract.py's "boundary_evidence" citation mode and
        GroundedAnswer._require_boundary_citations().
        """
        return Citation(
            evidence_id=be.evidence_id, excerpt=be.excerpt, citation_kind="boundary"
        )

    def to_governance_citation(self, be: BoundaryEvidence) -> Citation:
        """
        Resolve a registered BoundaryEvidence into a *governance-fact*
        Citation for a genuine "answer" about corpus/governance metadata
        (e.g. "is USB4 included in the Phase 1 corpus?",
        docs/USB_SPEC_QA_POC1_SCOPE.md lines 86-88) -- distinct from
        to_boundary_citation() because the response status is "answer", not
        "abstain": the same underlying registered fact (e.g. corpus.lock.yaml
        sources.usb4) can license two different, non-overlapping response
        shapes without duplicating the registry entry.
        """
        return Citation(
            evidence_id=be.evidence_id, excerpt=be.excerpt, citation_kind="governance"
        )
