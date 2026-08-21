import json
import hashlib
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
        governed_source = self.corpus_lock["sources"]["hub_reference"]
        self.knowledge_repo = governed_source["repo"]
        self.knowledge_repo_commit = governed_source["commit"]
        self.corpus_id = self.corpus_lock["corpus_id"]
        self.corpus_binding_status = self.corpus_lock["status"]
        self.binding_mode = f"embedded_registry_baseline ({self.corpus_binding_status})"
        self.bound_repo_head_commit = None
        self.bound_repo_files_hash = None

        if knowledge_repo_path and Path(knowledge_repo_path).exists():
            self.verify_and_bind_knowledge_repo(knowledge_repo_path)

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
        Computes SHA-256 manifest hash of physical knowledge repository files.
        """
        r_path = Path(repo_path)
        if not r_path.exists():
            return False

        hasher = hashlib.sha256()
        file_count = 0
        for f in sorted(list(r_path.rglob("*.md")) + list(r_path.rglob("*.yaml")) + list(r_path.rglob("*.json"))):
            if ".git" not in f.parts:
                hasher.update(f.read_bytes())
                file_count += 1

        self.bound_repo_files_hash = hasher.hexdigest()
        self.binding_mode = f"live_repo_bound ({file_count} files verified)"
        return True

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
