"""Machine-enforced content validator for shared dependency manifests.

``ScopeGuardrail`` (agent/governance/guardrails.py) only answers "is this
path allowed for this task?" -- it has no notion of what a diff to an
*allowed* file is permitted to contain. That is fine for files a single
task owns exclusively, but pyproject.toml and requirements.txt are shared,
repo-wide manifests: authorizing a task to write to them via
``allowed_paths`` alone would let it silently touch unrelated dependencies,
build-system config, or project metadata, with no enforcement beyond a
human-readable comment in contracts/gv100h-poc.yaml.

This module enforces, in code, the claim that a dependency-authorization
task (e.g. ``GV100H-M2-DEPS``) may only *additively* introduce specific
package names into these two files:

- requirements.txt: every existing non-blank line must survive unchanged;
  any new line's package name must be in the allowlist.
- pyproject.toml: every table/key outside ``[project.optional-dependencies]``
  must be byte-for-byte structurally identical to the base revision; within
  ``[project.optional-dependencies]``, existing dependency groups may only
  gain new entries (never lose or modify existing ones), and any brand-new
  dependency group may only contain allowlisted package names.

The allowlist itself lives in governance/approved_dependency_additions.json
so that authorizing a new package is its own reviewable, versioned change.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_PACKAGE_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass
class ValidationResult:
    is_valid: bool
    violations: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid

    @staticmethod
    def ok() -> "ValidationResult":
        return ValidationResult(is_valid=True, violations=[])

    @staticmethod
    def fail(*violations: str) -> "ValidationResult":
        return ValidationResult(is_valid=False, violations=list(violations))

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            violations=[*self.violations, *other.violations],
        )


def _package_name(dependency_spec: str) -> str:
    """Extracts the leading package name from a PEP 508-ish dependency string.

    ``"pdfplumber>=0.10"`` -> ``"pdfplumber"``; ``"fpdf2==2.7.0"`` ->
    ``"fpdf2"``; ``"pdfplumber[extra]>=1.0"`` -> ``"pdfplumber"``.
    """
    match = _PACKAGE_NAME_RE.match(dependency_spec)
    if not match:
        return dependency_spec.strip()
    name = match.group(1)
    bracket_index = name.find("[")
    return name if bracket_index == -1 else name[:bracket_index]


_EXTRAS_RE = re.compile(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*\[([^\]]*)\]")


def _package_identity(dependency_spec: str) -> "tuple[str, frozenset]":
    """Extracts ``(package_name, extras)`` -- e.g. ``"pydantic>=2.5"`` and
    ``"pydantic[email]>=2.6"`` have DIFFERENT identities, since adding an
    extras marker changes what actually gets installed (extra transitive
    dependencies) and must not be treated as an in-place version
    replacement of the plain package.
    """
    name = _package_name(dependency_spec)
    extras_match = _EXTRAS_RE.match(dependency_spec)
    if not extras_match:
        return (name, frozenset())
    extras = frozenset(e.strip() for e in extras_match.group(1).split(",") if e.strip())
    return (name, extras)


_DIRECT_REFERENCE_SUBSTRINGS = ("://", "git+", "hg+", "svn+", "bzr+")


def _rejects_direct_reference_source(dependency_spec: str) -> Optional[str]:
    """Returns a violation reason if ``dependency_spec`` is a PEP 508 direct
    reference / VCS URL instead of a plain version specifier, else ``None``.

    ``_package_name()`` only reads the leading token, so
    ``"pdfplumber @ https://attacker.invalid/pkg.whl"`` would otherwise be
    treated as the allowlisted ``pdfplumber`` package even though it
    actually redirects installation to an arbitrary, unreviewed source.
    """
    spec = dependency_spec.strip()
    if "@" in spec:
        return f"{spec!r} uses a direct URL/source reference (PEP 508 '@'), not a version specifier"
    lowered = spec.lower()
    for marker in _DIRECT_REFERENCE_SUBSTRINGS:
        if marker in lowered:
            return f"{spec!r} uses a direct URL/VCS source ({marker!r}), not a version specifier"
    return None


def validate_requirements_txt_diff(
    base_text: str,
    head_text: str,
    allowed_packages: Iterable[str],
    *,
    strict_additive_only: bool = True,
) -> ValidationResult:
    """Validates a requirements.txt diff.

    When ``strict_additive_only`` is True (the default, used for real
    task-scoped enforcement where the caller knows this file is exclusively
    owned by one dependency-authorization task), every existing line must
    survive unchanged and only allowlisted additions are permitted. When
    False (used for the repo-wide CI gate, which cannot attribute a diff to
    a specific task), removed/modified existing lines are not this check's
    concern -- only newly added lines are validated against the allowlist
    and against direct-reference/VCS sources, so unrelated tasks' legitimate
    manifest edits are not frozen by a task-specific allowlist.
    """
    allowed = set(allowed_packages)
    base_lines = [line.strip() for line in base_text.splitlines() if line.strip()]
    head_lines = [line.strip() for line in head_text.splitlines() if line.strip()]

    head_counts: Dict[str, int] = {}
    for line in head_lines:
        head_counts[line] = head_counts.get(line, 0) + 1

    violations: List[str] = []
    if strict_additive_only:
        remaining = dict(head_counts)
        for line in base_lines:
            if remaining.get(line, 0) > 0:
                remaining[line] -= 1
            else:
                violations.append(
                    f"requirements.txt: existing line was removed or modified: {line!r}"
                )

    base_counts: Dict[str, int] = {}
    for line in base_lines:
        base_counts[line] = base_counts.get(line, 0) + 1

    # A package identity (name + extras) only earns exemption "budget" for
    # each base line whose exact literal no longer survives in head -- one
    # unit of budget per removed literal, consumed one-for-one by added
    # lines of the SAME identity. This means: (1) merely adding a new
    # same-named line alongside an untouched original earns no budget (the
    # original was never removed); (2) removing one old literal exempts
    # exactly one same-identity replacement, not an unlimited number; and
    # (3) a replacement that changes extras (e.g. "pydantic>=2.5" ->
    # "pydantic[email]>=2.6") has a different identity and is NOT covered
    # by the plain package's removed budget, since extras change what
    # actually gets installed.
    removed_identity_budget: Dict["tuple[str, frozenset]", int] = {}
    for line, count in base_counts.items():
        missing = count - head_counts.get(line, 0)
        if missing > 0:
            identity = _package_identity(line)
            removed_identity_budget[identity] = removed_identity_budget.get(identity, 0) + missing

    added_extra: Dict[str, int] = dict(head_counts)
    for line, count in base_counts.items():
        added_extra[line] = added_extra.get(line, 0) - count

    for line, extra_count in added_extra.items():
        for _ in range(max(extra_count, 0)):
            direct_ref_reason = _rejects_direct_reference_source(line)
            if direct_ref_reason is not None:
                violations.append(f"requirements.txt: added line {direct_ref_reason}")
                continue
            # In lenient mode only, a genuine one-for-one replacement of a
            # removed same-identity line (e.g. "pyyaml>=6.0.1" ->
            # "pyyaml>=7.0.0") is a version-only modification, not a
            # brand-new package -- lenient mode's "not this task's concern"
            # policy for modifications already covers it. This must NEVER
            # apply in strict mode regardless.
            if not strict_additive_only:
                identity = _package_identity(line)
                if removed_identity_budget.get(identity, 0) > 0:
                    removed_identity_budget[identity] -= 1
                    continue
            package = _package_name(line)
            if package not in allowed:
                violations.append(
                    f"requirements.txt: added line {line!r} is not an approved "
                    f"addition (package {package!r} not in allowlist {sorted(allowed)})"
                )

    return ValidationResult(is_valid=not violations, violations=violations)


def _load_toml(text: str, *, label: str) -> Dict[str, Any]:
    if tomllib is None:
        raise RuntimeError(
            "dependency_manifest_diff_validator requires tomllib (stdlib, "
            "Python 3.11+) or the 'tomli' backport package (Python 3.10) "
            "to parse pyproject.toml, and neither is importable"
        )
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} is not valid TOML: {exc}") from exc


def _diff_dependency_array(
    base_deps: List[str],
    head_deps: List[str],
    allowed: set,
    *,
    strict_additive_only: bool,
    label: str,
) -> List[str]:
    """Diffs a single dependency array (``project.dependencies`` or one
    ``project.optional-dependencies`` group) against its base revision.

    Ordering and mode-gating here are the fix for three related bypasses:

    1. Any head entry not byte-identical to an existing base entry is
       checked for a direct URL/VCS source *before* anything else --
       including before comparing package names -- so replacing an
       already-approved package (e.g. ``pyyaml>=6.0.1``) with a
       same-named direct reference (``pyyaml @ https://attacker.invalid/...``)
       cannot slip past as "just an existing package".
    2. An entry is allowed to skip the allowlist check on the grounds that
       it is a version-only replacement ONLY when its (name, extras)
       identity was actually removed from head, and only one-for-one --
       each removed entry earns exactly one exemption "budget" unit
       (``removed_identity_budget``), consumed by at most one added entry
       of the same identity. This means: adding ``"pytest<1"`` alongside
       an untouched ``"pytest>=8.0.0"`` is a genuine new addition (no
       budget earned) and must still be allowlist-checked; removing
       ``"pydantic>=2.5"`` and adding ``"pydantic[email]>=2.6"`` is a
       *different* identity (extras changed what gets installed) and is
       not covered by the plain package's budget either. This exemption
       also only applies in **lenient** mode at all; in **strict**
       (task-scoped) mode every added entry must be allowlisted
       regardless of any package-identity overlap with base.
    """
    violations: List[str] = []
    base_set = set(base_deps)
    head_set = set(head_deps)
    # A package identity (name + extras) only earns exemption "budget" for
    # each base entry that did NOT survive verbatim into head -- one unit
    # of budget per removed entry, consumed one-for-one by added entries of
    # the SAME identity. This means: (1) merely adding a new same-named
    # entry alongside an untouched original earns no budget; (2) removing
    # one old entry exempts exactly one same-identity replacement, not an
    # unlimited number; and (3) a replacement that changes extras (e.g.
    # "pydantic>=2.5" -> "pydantic[email]>=2.6") has a different identity
    # and is NOT covered by the plain package's removed budget, since
    # extras change what actually gets installed.
    removed_identity_budget: Dict["tuple[str, frozenset]", int] = {}
    for dep in base_deps:
        if dep not in head_set:
            identity = _package_identity(dep)
            removed_identity_budget[identity] = removed_identity_budget.get(identity, 0) + 1

    if strict_additive_only:
        head_remaining = list(head_deps)
        for dep in base_deps:
            if dep in head_remaining:
                head_remaining.remove(dep)
            else:
                violations.append(
                    f"pyproject.toml: {label} existing entry was removed "
                    f"or modified: {dep!r}"
                )

    for dep in head_deps:
        if dep in base_set:
            continue
        direct_ref_reason = _rejects_direct_reference_source(dep)
        if direct_ref_reason is not None:
            violations.append(f"pyproject.toml: {label} added entry {direct_ref_reason}")
            continue
        if not strict_additive_only:
            identity = _package_identity(dep)
            if removed_identity_budget.get(identity, 0) > 0:
                removed_identity_budget[identity] -= 1
                continue
        package = _package_name(dep)
        if package not in allowed:
            violations.append(
                f"pyproject.toml: {label} added entry {dep!r} is not an "
                f"approved addition (package {package!r} not in allowlist "
                f"{sorted(allowed)})"
            )

    return violations


def validate_pyproject_toml_diff(
    base_text: str,
    head_text: str,
    allowed_packages: Iterable[str],
    *,
    strict_additive_only: bool = True,
) -> ValidationResult:
    """Validates a pyproject.toml diff. See ``validate_requirements_txt_diff``
    for the meaning of ``strict_additive_only``."""
    allowed = set(allowed_packages)
    base_doc = _load_toml(base_text, label="base pyproject.toml")
    head_doc = _load_toml(head_text, label="head pyproject.toml")

    base_optional = (
        base_doc.get("project", {}).get("optional-dependencies", {})
    )
    head_optional = (
        head_doc.get("project", {}).get("optional-dependencies", {})
    )

    violations: List[str] = []

    if strict_additive_only:
        base_without_optional = copy.deepcopy(base_doc)
        head_without_optional = copy.deepcopy(head_doc)
        base_without_optional.get("project", {}).pop("optional-dependencies", None)
        head_without_optional.get("project", {}).pop("optional-dependencies", None)
        if base_without_optional != head_without_optional:
            violations.append(
                "pyproject.toml: a change was made outside "
                "[project.optional-dependencies] -- only additive dependency "
                "entries are permitted for this task"
            )

    for group_name, base_group_deps in base_optional.items():
        if group_name not in head_optional:
            if strict_additive_only:
                violations.append(
                    f"pyproject.toml: optional-dependencies group {group_name!r} "
                    "was removed"
                )
            continue
        violations.extend(
            _diff_dependency_array(
                base_group_deps,
                head_optional[group_name],
                allowed,
                strict_additive_only=strict_additive_only,
                label=f"optional-dependencies[{group_name!r}]",
            )
        )

    for group_name, head_group_deps in head_optional.items():
        if group_name in base_optional:
            continue
        violations.extend(
            _diff_dependency_array(
                [],
                head_group_deps,
                allowed,
                strict_additive_only=strict_additive_only,
                label=f"new optional-dependencies group {group_name!r}",
            )
        )

    # project.dependencies (the main, non-optional dependency array) is
    # checked independently of strict_additive_only. In strict mode any
    # change to it is already caught by the "outside optional-dependencies
    # must be identical" check above, but that check is skipped in lenient
    # mode -- without this, a lenient (CI-wide) invocation would let an
    # unapproved or direct-URL package slip in through project.dependencies
    # while the docstring/contract claims lenient mode still rejects
    # unapproved dependency additions.
    base_dependencies = base_doc.get("project", {}).get("dependencies") or []
    head_dependencies = head_doc.get("project", {}).get("dependencies") or []
    violations.extend(
        _diff_dependency_array(
            base_dependencies,
            head_dependencies,
            allowed,
            strict_additive_only=strict_additive_only,
            label="project.dependencies",
        )
    )

    # build-system.requires is a dependency-bearing array outside the two
    # PEP 621 dependency arrays: packages listed there are installed by the
    # build backend when running e.g. "pip install .", so an unapproved or
    # direct-reference entry there bypasses the allowlist just as surely as
    # one in project.dependencies. Checked independently of
    # strict_additive_only for the same reason project.dependencies is: in
    # lenient (CI-wide) mode the "outside optional-dependencies must be
    # identical" whole-document check above is skipped entirely, so without
    # this explicit check a lenient invocation would never inspect
    # build-system.requires at all.
    base_build_requires = base_doc.get("build-system", {}).get("requires") or []
    head_build_requires = head_doc.get("build-system", {}).get("requires") or []
    violations.extend(
        _diff_dependency_array(
            base_build_requires,
            head_build_requires,
            allowed,
            strict_additive_only=strict_additive_only,
            label="build-system.requires",
        )
    )

    # PEP 621 lets a project mark "dependencies" (or an optional-dependencies
    # group) as build-backend-resolved via project.dynamic instead of listing
    # them literally in this file -- e.g. setuptools' own
    # [tool.setuptools.dynamic].dependencies can point at an arbitrary
    # external file. This validator only ever inspects the literal arrays
    # above, so it has no way to enumerate or allowlist packages sourced
    # that way, backend-agnostically, for every declared or possible build
    # backend. Reproduced by Codex: in lenient mode, moving
    # project.dependencies to dynamic and adding a
    # [tool.setuptools.dynamic] pointer to an attacker-controlled file
    # passed validation because the (now empty/absent) static array showed
    # no unapproved addition. Fail closed unconditionally rather than trying
    # to special-case every backend's dynamic-source mechanism.
    head_dynamic = set(head_doc.get("project", {}).get("dynamic") or [])
    dynamic_dependency_fields = {"dependencies", "optional-dependencies"}
    dynamic_deps_declared = head_dynamic & dynamic_dependency_fields
    if dynamic_deps_declared:
        violations.append(
            "pyproject.toml: project.dynamic declares "
            f"{sorted(dynamic_deps_declared)} as build-backend-resolved; this "
            "validator cannot inspect dependencies sourced outside "
            "project.dependencies/project.optional-dependencies (e.g. "
            "[tool.setuptools.dynamic] or an equivalent backend mechanism "
            "pointing at an external file), so any pyproject.toml declaring "
            "dynamic dependencies is rejected -- declare dependencies "
            "statically instead"
        )

    return ValidationResult(is_valid=not violations, violations=violations)


def load_allowed_packages(
    allowlist_path: Path, task_id: Optional[str] = None
) -> List[str]:
    """Loads the allowlist file, returning the union of allowed packages.

    When ``task_id`` is given, only that task's allowlist is used; otherwise
    the union across every declared task is used (the conservative default,
    since a real PR's diff is not reliably associated with a single task_id).
    """
    data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", {})
    if task_id is not None:
        if task_id not in tasks:
            raise KeyError(
                f"task {task_id!r} not declared in {allowlist_path}; "
                f"available: {sorted(tasks)}"
            )
        return list(tasks[task_id].get("allowed_packages", []))

    combined: List[str] = []
    for task_def in tasks.values():
        combined.extend(task_def.get("allowed_packages", []))
    return combined


def _git_show(ref: str, path: str, *, repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FileNotFoundError(
            f"could not read {path!r} at ref {ref!r}: {result.stderr.strip()}"
        )
    return result.stdout


def validate_manifests_against_ref(
    base_ref: str,
    allowlist_path: Path,
    task_id: Optional[str] = None,
    *,
    repo_root: Optional[Path] = None,
    strict_additive_only: bool = True,
) -> ValidationResult:
    effective_repo_root = repo_root or PROJECT_ROOT
    allowed_packages = load_allowed_packages(allowlist_path, task_id=task_id)
    overall = ValidationResult.ok()

    requirements_path = effective_repo_root / "requirements.txt"
    try:
        base_requirements = _git_show(base_ref, "requirements.txt", repo_root=effective_repo_root)
    except FileNotFoundError:
        base_requirements = ""
    head_requirements = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    if base_requirements != head_requirements:
        overall = overall.merge(
            validate_requirements_txt_diff(
                base_requirements,
                head_requirements,
                allowed_packages,
                strict_additive_only=strict_additive_only,
            )
        )

    pyproject_path = effective_repo_root / "pyproject.toml"
    try:
        base_pyproject = _git_show(base_ref, "pyproject.toml", repo_root=effective_repo_root)
    except FileNotFoundError:
        base_pyproject = ""
    head_pyproject = pyproject_path.read_text(encoding="utf-8") if pyproject_path.exists() else ""
    if base_pyproject != head_pyproject:
        overall = overall.merge(
            validate_pyproject_toml_diff(
                base_pyproject,
                head_pyproject,
                allowed_packages,
                strict_additive_only=strict_additive_only,
            )
        )

    return overall


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="git ref to diff pyproject.toml/requirements.txt against (default: origin/main)",
    )
    parser.add_argument(
        "--allowlist",
        default=str(PROJECT_ROOT / "governance" / "approved_dependency_additions.json"),
        help="path to the approved-dependency-additions allowlist JSON file",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="restrict to a single task's allowlist entry instead of the union of all tasks",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help=(
            "do not reject removed/modified existing manifest lines (used by "
            "the repo-wide CI gate, which cannot attribute a diff to a single "
            "dependency-authorization task); still rejects unapproved or "
            "direct-reference/VCS-sourced additions"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=str(PROJECT_ROOT),
        help=(
            "repository root to read requirements.txt/pyproject.toml from and "
            "to run 'git show' in (default: this script's own repo). Must be "
            "set explicitly when running a copy of this script extracted to a "
            "path outside the repo (e.g. a trusted base-ref copy fetched via "
            "'git show' into a temp file), since PROJECT_ROOT is otherwise "
            "derived from __file__ and would silently point at the temp "
            "file's directory instead of the actual checkout."
        ),
    )
    args = parser.parse_args(argv)

    result = validate_manifests_against_ref(
        args.base_ref,
        Path(args.allowlist),
        task_id=args.task,
        repo_root=Path(args.repo_root),
        strict_additive_only=not args.lenient,
    )
    if result.is_valid:
        print("[PASS] Dependency manifest diff validation passed.")
        return 0

    print("[FAIL] Dependency manifest diff validation failed:")
    for violation in result.violations:
        print(f"  - {violation}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
