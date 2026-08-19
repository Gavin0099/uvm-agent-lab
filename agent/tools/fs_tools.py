import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from agent.governance.guardrails import ScopeGuardrail


class GovernedFileSystemTools:
    """
    File system manipulation tools protected by ScopeGuardrails.
    """

    def __init__(self, guardrail: Optional[ScopeGuardrail] = None, root_dir: str = "."):
        self.guardrail = guardrail
        self.root_dir = Path(root_dir).resolve()

    def _resolve_contained(self, file_path: str) -> Optional[Path]:
        full_path = (self.root_dir / file_path).resolve()
        try:
            full_path.relative_to(self.root_dir)
        except ValueError:
            return None
        return full_path

    def read_file(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        if self.guardrail is not None:
            allowed, report = self.guardrail.check_path_access(file_path, action="read")
            if not allowed:
                return {
                    "status": "governance_violation",
                    "violations": [v.model_dump() for v in report.violations],
                    "message": f"Scope violation reading '{file_path}'.",
                }
        full_path = self._resolve_contained(file_path)
        if full_path is None:
            return {"status": "error", "message": f"Path '{file_path}' escapes workspace root."}
        if not full_path.exists():
            return {"status": "error", "message": f"File '{file_path}' does not exist."}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if start_line is not None or end_line is not None:
                s = max(0, (start_line or 1) - 1)
                e = end_line or len(lines)
                content = "".join(lines[s:e])
            else:
                content = "".join(lines)
            return {"status": "success", "content": content, "lines_count": len(lines)}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        # 1. Pre-write Sidecar Interception (if active)
        if self.guardrail is not None:
            allowed, report = self.guardrail.check_path_access(file_path, action="write")
            if not allowed:
                return {
                    "status": "governance_violation",
                    "violations": [v.model_dump() for v in report.violations],
                    "message": f"Scope violation writing to '{file_path}'."
                }

        # 2. Strict OS-level containment within root_dir
        full_path = self._resolve_contained(file_path)
        if full_path is None:
            return {
                "status": "governance_violation",
                "violations": [{"code": "ESCAPE_ATTEMPT", "message": f"Attempted write outside root: {file_path}"}],
                "message": f"Workspace escape prevented: '{file_path}'."
            }

        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "success", "file_path": file_path, "bytes_written": len(content)}

