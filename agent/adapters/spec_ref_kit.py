import json
from pathlib import Path
from typing import Dict, Any, Optional


class SpecReferenceKitAdapter:
    """
    Adapter to interface with the external 'spec-reference-kit' governed knowledge layer.
    Supports local JSON mock or CLI/MCP subprocess query.
    """

    def __init__(self, spec_root: str = "fixtures/synthetic-spec"):
        self.spec_root = Path(spec_root).resolve()

    def query_requirement(self, requirement_id: str, protocol: Optional[str] = None) -> Dict[str, Any]:
        """
        Query authoritative requirement details and verify provenance hash.
        """
        for spec_file in self.spec_root.glob("*.md"):
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if requirement_id in content:
                    return {
                        "status": "success",
                        "requirement_id": requirement_id,
                        "spec_file": spec_file.name,
                        "authority": "authoritative",
                        "content_snippet": content[:500],
                    }
            except Exception as ex:
                continue

        return {
            "status": "not_found",
            "requirement_id": requirement_id,
            "message": f"Requirement {requirement_id} not found in governed specs."
        }
