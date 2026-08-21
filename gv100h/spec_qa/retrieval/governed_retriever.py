import json
import hashlib
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import yaml


class GovernedEvidence(BaseModel):
    evidence_id: str
    authority_level: str  # "authoritative", "informative", "derived"
    scope: str            # "USB_2_0", "USB_3_X", "USB_HUB_COMMON"
    claim_level: str      # "normative_requirement", "informative_guideline"
    section: str
    title: str
    content: str


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
            content="In USB 3.x Hub specifications, PORT_POWER feature selector value is 8 (0x0008). Used with SetPortFeature to enable VBUS power to the downstream port."
        ),
        GovernedEvidence(
            evidence_id="USB2-FEAT-PORT_POWER",
            authority_level="authoritative",
            scope="USB_2_0",
            claim_level="normative_requirement",
            section="11.24.2.1",
            title="Hub Class Feature Selectors (USB 2.0)",
            content="In USB 2.0 Hub specifications, PORT_POWER feature selector value is 8 (0x0008)."
        ),
        GovernedEvidence(
            evidence_id="USB3-FEAT-PORT_LINK_STATE",
            authority_level="authoritative",
            scope="USB_3_X",
            claim_level="normative_requirement",
            section="10.16.2.2",
            title="Port Link State Feature Selector (USB 3.x)",
            content="PORT_LINK_STATE feature selector value is 5 (0x0005) in USB 3.x. Not applicable to USB 2.0 (USB 3.x 專屬，在 USB 2.0 架構下無效，不支援且不適用)."
        ),
        GovernedEvidence(
            evidence_id="USB3-HUB-DESC-FORMAT",
            authority_level="authoritative",
            scope="USB_3_X",
            claim_level="normative_requirement",
            section="10.15.2.1",
            title="USB 3.x SuperSpeed Hub Descriptor",
            content="bDescriptorType is 0x2A for SuperSpeed Hub Descriptor (USB 3.x), distinguishing it from USB 2.0 Hub Descriptor (0x29). USB 3.x Hub 不能直接使用 0x29."
        ),
        GovernedEvidence(
            evidence_id="USB2-HUB-DESC-FORMAT",
            authority_level="authoritative",
            scope="USB_2_0",
            claim_level="normative_requirement",
            section="11.23.2.1",
            title="USB 2.0 Hub Descriptor",
            content="bDescriptorType is 0x29 for USB 2.0 Hub Descriptor. 收到 0x2A 在 USB 2.0 為未定義錯誤。"
        )
    ]

    def __init__(
        self,
        knowledge_repo_path: Optional[str] = None,
        corpus_lock_path: Optional[str] = None,
    ):
        self.corpus_lock_path = (
            Path(corpus_lock_path).resolve()
            if corpus_lock_path
            else self.DEFAULT_CORPUS_LOCK_PATH
        )
        self.corpus_lock = self._load_corpus_lock(self.corpus_lock_path)
        self.corpus_lock_validation = self.validate_corpus_lock(self.corpus_lock)
        self.qualification_blocked = self.corpus_lock_validation["qualification_blocked"]
        self.qualification_block_reasons = self.corpus_lock_validation["block_reasons"]
        governed_source = self.corpus_lock["sources"]["hub_reference"]
        self.knowledge_repo = governed_source["repo"]
        self.knowledge_repo_commit = governed_source["commit"]
        self.corpus_id = self.corpus_lock["corpus_id"]
        self.corpus_binding_status = self.corpus_lock["status"]
        self.binding_mode = f"embedded_registry_baseline ({self.corpus_binding_status})"
        self.bound_repo_head_commit = None
        self.bound_repo_files_hash = None

        if knowledge_repo_path:
            if not Path(knowledge_repo_path).exists():
                raise FileNotFoundError(f"governed reference path does not exist: {knowledge_repo_path}")
            self.verify_and_bind_knowledge_repo(knowledge_repo_path)

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
        self.binding_mode = f"live_repo_bound ({file_count} files verified)"
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

    def query(self, query_text: str, target_scope: Optional[str] = None) -> List[GovernedEvidence]:
        q_lower = query_text.lower()
        scored_results = []

        for ev in self.EVIDENCE_REGISTRY:
            score = 0
            if target_scope and ev.scope == target_scope:
                score += 5

            if "descriptor" in q_lower or "描述符" in q_lower or "bdescriptortype" in q_lower:
                if "DESC" in ev.evidence_id:
                    score += 15
            if "port_power" in q_lower or "電源" in q_lower:
                if "PORT_POWER" in ev.evidence_id:
                    score += 15
            if "port_link_state" in q_lower or "link" in q_lower:
                if "PORT_LINK_STATE" in ev.evidence_id:
                    score += 15
            if "10.16.2.1" in q_lower and "10.16.2.1" in ev.section:
                score += 20
            if "10.16.2.2" in q_lower and "10.16.2.2" in ev.section:
                score += 20
            if "11.23" in q_lower and "11.23" in ev.section:
                score += 20
            if "10.15" in q_lower and "10.15" in ev.section:
                score += 20

            for token in q_lower.replace("？", " ").replace("。", " ").split():
                if len(token) > 1 and (token in ev.title.lower() or token in ev.content.lower() or token in ev.section):
                    score += 2

            if score > 0:
                scored_results.append((score, ev))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results]

    def get_evidence_by_id(self, evidence_id: str) -> Optional[GovernedEvidence]:
        for ev in self.EVIDENCE_REGISTRY:
            if ev.evidence_id == evidence_id:
                return ev
        return None
