import os
from pathlib import Path
from typing import List, Tuple, Optional
from .policy import GovernanceViolationCode, GovernanceSeverity, GovernanceReport


class ScopeGuardrail:
    """
    Enforces sandbox scope boundaries with canonical path and symlink resolution.
    Prevents unauthorized reads/writes to forbidden paths (such as RTL source)
    or out-of-scope files, and defends against path traversal (../, ..\\) and symlink escapes.
    """

    def __init__(self, allowed_paths: List[str], forbidden_paths: List[str], base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.allowed_paths = [self._normalize_rule_path(p) for p in allowed_paths]
        self.forbidden_paths = [self._normalize_rule_path(p) for p in forbidden_paths]

    def _normalize_rule_path(self, p: str) -> str:
        clean = p.replace("\\", "/").strip().strip("/")
        return clean.lower()

    def _resolve_canonical_relative(self, target_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves target_path against base_dir and returns (canonical_relative_path_lower, error_message).
        If the resolved path escapes base_dir, returns (None, error_message).
        Backslashes are treated as separators on every platform so Windows-style
        traversal (``..\\``) cannot collapse into a single POSIX filename.
        """
        try:
            target = Path(str(target_path).replace("\\", "/"))
            if target.is_absolute():
                resolved = target.resolve()
            else:
                resolved = (self.base_dir / target).resolve()

            # Check if resolved path is strictly within base_dir
            try:
                rel = resolved.relative_to(self.base_dir)
                rel_str = rel.as_posix().lower()
                return rel_str, None
            except ValueError:
                return None, f"Path traversal escape detected: '{target_path}' resolves to '{resolved}' which is outside base directory '{self.base_dir}'."
        except Exception as e:
            return None, f"Path resolution failed for '{target_path}': {str(e)}"

    def normalize_relative_path(self, target_path: str) -> Optional[str]:
        """Public wrapper around the canonical-relative resolution used by
        ``check_path_access()``, so callers that need to compare a raw
        (possibly ``./``-prefixed, absolute, or backslash-separated) path
        against a fixed set of guarded filenames use the same normalization
        the scope gate itself uses, instead of a naive string match that a
        differently-formatted equivalent path can silently bypass.

        Returns the lowercased, POSIX-style, base_dir-relative path, or
        ``None`` if the path could not be resolved/escapes base_dir.
        """
        rel, err = self._resolve_canonical_relative(target_path)
        return rel if err is None else None

    def check_path_access(self, target_path: str, action: str = "write") -> Tuple[bool, GovernanceReport]:
        report = GovernanceReport()
        clean_rel, escape_err = self._resolve_canonical_relative(target_path)

        if escape_err or clean_rel is None:
            report.add_violation(
                code=GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS,
                severity=GovernanceSeverity.FATAL,
                message=escape_err or f"Invalid path '{target_path}'.",
                target=target_path,
            )
            return False, report

        # 1. Check against forbidden paths
        for forbidden in self.forbidden_paths:
            if clean_rel == forbidden or clean_rel.startswith(forbidden + "/"):
                report.add_violation(
                    code=GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH,
                    severity=GovernanceSeverity.FATAL,
                    message=f"Access denied: Resolved path '{clean_rel}' is inside forbidden directory '{forbidden}'.",
                    target=target_path,
                )
                return False, report

        # 2. Check if within allowed paths
        is_allowed = False
        for allowed in self.allowed_paths:
            if clean_rel == allowed or clean_rel.startswith(allowed + "/"):
                is_allowed = True
                break

        if not is_allowed:
            report.add_violation(
                code=GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS,
                severity=GovernanceSeverity.FATAL,
                message=f"Access denied: Resolved path '{clean_rel}' is not within any allowed paths {self.allowed_paths}.",
                target=target_path,
            )
            return False, report

        return True, report
