"""Tests for validators/dependency_manifest_diff_validator.py.

Covers the two enforcement surfaces described in the module docstring:
requirements.txt line-level additive-only diffing, and pyproject.toml
structural diffing scoped to [project.optional-dependencies].
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validators.dependency_manifest_diff_validator import (  # noqa: E402
    load_allowed_packages,
    validate_manifests_against_ref,
    validate_pyproject_toml_diff,
    validate_requirements_txt_diff,
)

ALLOWED = ["pdfplumber", "fpdf2"]


# ---------------------------------------------------------------------------
# requirements.txt
# ---------------------------------------------------------------------------


def test_requirements_txt_additive_only_change_passes():
    base = "pyyaml>=6.0.1\njsonschema>=4.20.0\n"
    head = "pyyaml>=6.0.1\njsonschema>=4.20.0\npdfplumber>=0.10\nfpdf2>=2.7.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert result.is_valid, result.violations


def test_requirements_txt_removed_line_fails():
    base = "pyyaml>=6.0.1\njsonschema>=4.20.0\n"
    head = "pyyaml>=6.0.1\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not result.is_valid
    assert any("removed or modified" in v for v in result.violations)


def test_requirements_txt_modified_line_fails():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=7.0.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not result.is_valid
    assert any("removed or modified" in v for v in result.violations)


def test_requirements_txt_unapproved_addition_fails():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\nrequests>=2.31.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_added_comment_line_passes():
    """Regression for a Codex P2 finding: a documentation-only comment line
    has no install-time meaning and must not be treated as a dependency
    spec. Reproduced with "# pin parser dependencies", which was previously
    rejected as an unapproved package because its "package name" became the
    entire comment text."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\n# pin parser dependencies\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert result.is_valid, result.violations

    lenient_result = validate_requirements_txt_diff(
        base, head, ALLOWED, strict_additive_only=False
    )
    assert lenient_result.is_valid, lenient_result.violations


def test_requirements_txt_removed_comment_line_does_not_fail_strict_mode():
    base = "# pin parser dependencies\npyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert result.is_valid, result.violations


def test_requirements_txt_no_change_passes():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert result.is_valid


def test_requirements_txt_direct_url_reference_fails_even_if_name_allowed():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\npdfplumber @ https://attacker.invalid/pkg.whl\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not result.is_valid
    assert any("direct URL/source reference" in v for v in result.violations)


def test_requirements_txt_vcs_reference_fails_even_if_name_allowed():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\ngit+https://github.com/attacker/pdfplumber.git\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not result.is_valid
    assert any("direct URL/VCS source" in v for v in result.violations)


def test_requirements_txt_lenient_mode_ignores_removed_line_but_checks_additions():
    base = "pyyaml>=6.0.1\njsonschema>=4.20.0\n"
    head = "pyyaml>=6.0.1\n"  # jsonschema removed: not this task's concern in lenient mode
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_requirements_txt_lenient_mode_still_rejects_unapproved_addition():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=7.0.0\nrequests>=2.31.0\n"  # modified line + unapproved addition
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)
    assert not any("removed or modified" in v for v in result.violations)


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------

BASE_PYPROJECT = """
[project]
name = "uvm-agent-lab"
version = "0.1.0"
dependencies = ["pyyaml>=6.0.1"]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""


def test_pyproject_new_group_with_allowed_packages_passes():
    head = BASE_PYPROJECT + '\npdf = ["pdfplumber>=0.10", "fpdf2>=2.7.0"]\n'
    # Insert the new group correctly under [project.optional-dependencies]
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0"]\npdf = ["pdfplumber>=0.10", "fpdf2>=2.7.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert result.is_valid, result.violations


def test_pyproject_existing_group_gains_allowed_entry_passes():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "pdfplumber>=0.10"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert result.is_valid, result.violations


def test_pyproject_existing_group_gains_unapproved_entry_fails():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "requests>=2.31.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_pyproject_new_group_with_unapproved_package_fails():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0"]\npdf = ["requests>=2.31.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_pyproject_removed_existing_entry_fails():
    head = BASE_PYPROJECT.replace('dev = ["pytest>=8.0.0"]', "dev = []")
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("removed or modified" in v for v in result.violations)


def test_pyproject_removed_optional_group_fails():
    head = BASE_PYPROJECT.replace('dev = ["pytest>=8.0.0"]\n', "")
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("was removed" in v for v in result.violations)


def test_pyproject_unrelated_section_change_fails():
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "click>=8.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("outside [project.optional-dependencies]" in v for v in result.violations)


def test_pyproject_build_system_change_fails():
    head = BASE_PYPROJECT + "\n[build-system]\nrequires = [\"setuptools>=61.0\"]\n"
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("outside [project.optional-dependencies]" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_unapproved_build_system_requires_addition():
    """Regression for a Codex P1 finding: in lenient mode the "outside
    optional-dependencies must be identical" whole-document check above is
    skipped entirely, so without an explicit, unconditional check on
    build-system.requires, a lenient (CI-wide) invocation would let an
    unapproved package slip in through the build backend's own requirements
    -- which pip installs and executes during "pip install .", exactly like
    an unapproved entry in project.dependencies."""
    base_with_build_system = BASE_PYPROJECT + '\n[build-system]\nrequires = ["setuptools>=61.0"]\n'
    head = base_with_build_system.replace(
        'requires = ["setuptools>=61.0"]',
        'requires = ["setuptools>=61.0", "requests>=2.31.0"]',
    )
    result = validate_pyproject_toml_diff(
        base_with_build_system, head, ALLOWED, strict_additive_only=False
    )
    assert not result.is_valid
    assert any(
        "build-system.requires added entry" in v and "not an approved addition" in v
        for v in result.violations
    )


def test_pyproject_lenient_mode_rejects_direct_url_in_build_system_requires():
    base_with_build_system = BASE_PYPROJECT + '\n[build-system]\nrequires = ["setuptools>=61.0"]\n'
    head = base_with_build_system.replace(
        'requires = ["setuptools>=61.0"]',
        'requires = ["setuptools>=61.0", "pdfplumber @ https://attacker.invalid/pkg.whl"]',
    )
    result = validate_pyproject_toml_diff(
        base_with_build_system, head, ALLOWED, strict_additive_only=False
    )
    assert not result.is_valid
    assert any(
        "build-system.requires added entry" in v and "direct URL/source reference" in v
        for v in result.violations
    )


def test_pyproject_lenient_mode_allows_approved_build_system_requires_addition():
    base_with_build_system = BASE_PYPROJECT + '\n[build-system]\nrequires = ["setuptools>=61.0"]\n'
    head = base_with_build_system.replace(
        'requires = ["setuptools>=61.0"]',
        'requires = ["setuptools>=61.0", "pdfplumber>=0.10"]',
    )
    result = validate_pyproject_toml_diff(
        base_with_build_system, head, ALLOWED, strict_additive_only=False
    )
    assert result.is_valid, result.violations


def test_pyproject_lenient_mode_rejects_dynamic_dependencies():
    """Regression for a Codex P1 finding: --lenient mode only inspected the
    three hard-coded static arrays (project.dependencies,
    project.optional-dependencies, build-system.requires). A PR could move
    project.dependencies to project.dynamic and point
    [tool.setuptools.dynamic].dependencies at an arbitrary external file
    (e.g. deps.txt) whose contents this validator never reads, letting an
    unapproved package be installed once setuptools resolves it -- while
    the static array check saw only a removal (ignored in lenient mode)."""
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        (
            'dynamic = ["dependencies"]\n\n'
            "[tool.setuptools.dynamic]\n"
            'dependencies = {file = ["deps.txt"]}'
        ),
    )
    result = validate_pyproject_toml_diff(
        BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False
    )
    assert not result.is_valid
    assert any("project.dynamic" in v and "dependencies" in v for v in result.violations)

    strict_result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not strict_result.is_valid


def test_pyproject_no_change_passes():
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, BASE_PYPROJECT, ALLOWED)
    assert result.is_valid


def test_pyproject_direct_url_reference_fails_even_if_name_allowed():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "pdfplumber @ https://attacker.invalid/pkg.whl"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED)
    assert not result.is_valid
    assert any("direct URL/source reference" in v for v in result.violations)


def test_pyproject_lenient_mode_ignores_unrelated_section_change():
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=7.0.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_pyproject_lenient_mode_still_rejects_unapproved_new_entry():
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=7.0.0"]',
    ).replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "requests>=2.31.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)
    assert not any("outside [project.optional-dependencies]" in v for v in result.violations)


def test_pyproject_lenient_mode_still_rejects_unapproved_addition_to_main_dependencies():
    """Regression for the P2 Codex finding: lenient mode's "skip changes
    outside optional-dependencies" must not let an unapproved package slip
    into project.dependencies (the main, non-optional array) unvalidated."""
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "requests>=2.31.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("project.dependencies added entry" in v and "not an approved addition" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_direct_url_in_main_dependencies():
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pdfplumber @ https://attacker.invalid/pkg.whl"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("project.dependencies added entry" in v and "direct URL/source reference" in v for v in result.violations)


def test_pyproject_lenient_mode_version_bump_of_existing_main_dependency_passes():
    """A version-only change to an already-present main dependency is a
    modification, not a new unreviewed package -- it must not be flagged as
    an unapproved addition just because its full literal spec string
    changed."""
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=7.0.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_pyproject_lenient_mode_rejects_same_name_direct_url_replacement_in_main_dependencies():
    """Regression for the P1 Codex finding: replacing an already-present
    package with a same-named direct URL/VCS reference
    (e.g. "pyyaml @ https://attacker.invalid/pkg.whl") must still be
    rejected in lenient mode -- the package-name match used to permit
    version bumps must not also permit a source-swap bypass."""
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml @ https://attacker.invalid/pkg.whl"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "project.dependencies added entry" in v and "direct URL/source reference" in v
        for v in result.violations
    )


def test_pyproject_lenient_mode_rejects_same_name_direct_url_replacement_in_optional_group():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest @ https://attacker.invalid/pkg.whl"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "optional-dependencies" in v and "direct URL/source reference" in v
        for v in result.violations
    )


def test_pyproject_lenient_mode_version_bump_of_existing_optional_dependency_passes():
    """Regression for the P2 Codex finding: a version-only change to an
    already-present optional-dependency entry (e.g. "pytest>=8.0.0" ->
    "pytest>=9.0.0") must not be rejected as an unapproved new package in
    lenient mode -- it is a modification, which lenient mode's "not this
    task's concern" policy explicitly permits."""
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=9.0.0"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations



# ---------------------------------------------------------------------------
# allowlist loading
# ---------------------------------------------------------------------------


def test_load_allowed_packages_by_task(tmp_path):
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "tasks": {
                    "GV100H-M2-DEPS": {"allowed_packages": ["pdfplumber", "fpdf2"]},
                    "OTHER-TASK": {"allowed_packages": ["numpy"]},
                }
            }
        ),
        encoding="utf-8",
    )
    assert set(load_allowed_packages(allowlist, task_id="GV100H-M2-DEPS")) == {
        "pdfplumber",
        "fpdf2",
    }
    assert set(load_allowed_packages(allowlist)) == {"pdfplumber", "fpdf2", "numpy"}


def test_load_allowed_packages_unknown_task_raises(tmp_path):
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(json.dumps({"tasks": {}}), encoding="utf-8")
    with pytest.raises(KeyError):
        load_allowed_packages(allowlist, task_id="NOPE")


# ---------------------------------------------------------------------------
# ref-based integration (uses a throwaway temp git repo, not this repo)
# ---------------------------------------------------------------------------


def _init_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)


def test_validate_manifests_against_ref_detects_unapproved_change(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    (repo_dir / "requirements.txt").write_text("pyyaml>=6.0.1\n", encoding="utf-8")
    (repo_dir / "pyproject.toml").write_text(BASE_PYPROJECT, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo_dir, check=True)

    # Additive-only change: should pass.
    (repo_dir / "requirements.txt").write_text(
        "pyyaml>=6.0.1\npdfplumber>=0.10\n", encoding="utf-8"
    )
    allowlist = repo_dir / "allowlist.json"
    allowlist.write_text(
        json.dumps({"tasks": {"T": {"allowed_packages": ["pdfplumber"]}}}),
        encoding="utf-8",
    )
    passing = validate_manifests_against_ref(
        "HEAD", allowlist, task_id="T", repo_root=repo_dir
    )
    assert passing.is_valid, passing.violations

    # Unapproved change: should fail.
    (repo_dir / "requirements.txt").write_text(
        "pyyaml>=6.0.1\nrequests>=2.31.0\n", encoding="utf-8"
    )
    failing = validate_manifests_against_ref(
        "HEAD", allowlist, task_id="T", repo_root=repo_dir
    )
    assert not failing.is_valid
    assert any("not an approved addition" in v for v in failing.violations)


def test_cli_repo_root_flag_targets_explicit_repo_not_script_location(tmp_path):
    """Regression for a Codex P1 on the CI wiring (not this module's default
    behavior): CI runs a copy of this script extracted via 'git show' into a
    mktemp path outside the repo, so it can execute a trusted base-ref
    version rather than the PR's own (possibly tampered) copy. Without an
    explicit --repo-root override, PROJECT_ROOT (derived from __file__)
    would silently resolve to the temp copy's own directory instead of the
    real checkout, breaking requirements.txt/pyproject.toml resolution and
    'git show' ref lookups. This proves --repo-root makes that override
    work when the script runs from an unrelated location."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_repo(repo_dir)
    (repo_dir / "requirements.txt").write_text("pyyaml>=6.0.1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo_dir, check=True)

    (repo_dir / "requirements.txt").write_text(
        "pyyaml>=6.0.1\nrequests>=2.31.0\n", encoding="utf-8"
    )
    allowlist = repo_dir / "allowlist.json"
    allowlist.write_text(
        json.dumps({"tasks": {"T": {"allowed_packages": ["pdfplumber"]}}}),
        encoding="utf-8",
    )

    # Copy the validator script somewhere unrelated to repo_dir, simulating
    # a 'git show BASE_REF:validators/...py' extraction into a mktemp file.
    script_copy_dir = tmp_path / "elsewhere"
    script_copy_dir.mkdir()
    script_copy = script_copy_dir / "trusted_validator.py"
    script_copy.write_text(
        (PROJECT_ROOT / "validators" / "dependency_manifest_diff_validator.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script_copy),
            "--base-ref",
            "HEAD",
            "--allowlist",
            str(allowlist),
            "--task",
            "T",
            "--repo-root",
            str(repo_dir),
            "--lenient",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "not an approved addition" in result.stdout


# ---------------------------------------------------------------------------
# strict-mode same-name-addition and Python 3.10 (tomli fallback) coverage
# ---------------------------------------------------------------------------


def test_pyproject_strict_mode_rejects_same_name_addition_alongside_untouched_entry():
    """Regression for the round-5 Codex P1 finding: in STRICT (task-scoped)
    mode, an added entry must be allowlist-checked even if its package name
    matches an untouched existing entry -- e.g. adding "pytest<1" alongside
    an unmodified "pytest>=8.0.0" is a genuine new addition (the old entry
    is not being replaced), not a version-bump modification, and must not
    silently pass just because the package name is already present."""
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "pytest<1"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=True)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_strict_mode_rejects_same_name_addition_alongside_untouched_entry():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\npyyaml<5\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=True)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_lenient_mode_version_bump_of_existing_dependency_passes():
    """Regression for the round-5 Codex P2 finding: a version-only change
    to an already-present requirements.txt line (e.g. "pyyaml>=6.0.1" ->
    "pyyaml>=7.0.0") must not be rejected as an unapproved new package in
    lenient mode."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=7.0.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_pyproject_lenient_mode_rejects_same_name_addition_alongside_untouched_entry():
    """Regression for the round-6 Codex P2 finding: the lenient-mode
    same-name exemption must require the OLD entry to have actually been
    removed, not just share a package name with something still present.
    Adding "pydantic[email]" alongside an untouched "pydantic>=2.5.0" is a
    genuine new addition (extra transitive deps, installed before this
    gate could reject it) and must still be allowlist-checked even in
    lenient mode."""
    base = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
    )
    head = base.replace(
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0", "pydantic[email]"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "project.dependencies added entry" in v and "declares extras" in v
        for v in result.violations
    )


def test_pyproject_lenient_mode_rejects_same_name_addition_in_optional_group_alongside_untouched_entry():
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=8.0.0", "pytest<1"]',
    )
    result = validate_pyproject_toml_diff(BASE_PYPROJECT, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_lenient_mode_rejects_same_name_addition_alongside_untouched_entry():
    base = "pytest>=8.0.0\n"
    head = "pytest>=8.0.0\npytest<1\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_extra_after_same_name_version_bump():
    """A version bump consumes one replacement. Adding pydantic[email] in
    the same diff is a second same-name addition and must still fail."""
    base = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
    )
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=3.0", "pydantic[email]"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("pydantic[email]" in v and "declares extras" in v for v in result.violations)


def test_requirements_txt_lenient_mode_rejects_extra_pin_after_same_name_version_bump():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=7.0.0\npyyaml<8\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_extras_replacement_of_removed_entry():
    """Regression for the round-7 Codex P1 finding: replacing a removed
    entry with a same-named entry that ADDS an extras marker (e.g.
    "pydantic>=2.5" -> "pydantic[email]>=2.6") is not a version-only
    replacement -- extras change what actually gets installed (extra
    transitive dependencies) -- and must still be allowlist-checked even
    though the plain package name was "removed"."""
    base = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
    )
    head = base.replace(
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic[email]>=2.6.0"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "project.dependencies added entry" in v and "declares extras" in v
        for v in result.violations
    )


def test_requirements_txt_lenient_mode_rejects_extras_replacement_of_removed_line():
    base = "pydantic>=2.5.0\n"
    head = "pydantic[email]>=2.6.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("declares extras" in v for v in result.violations)


def test_pyproject_lenient_mode_limits_same_identity_exemption_to_one_removal():
    """Regression for the round-7 Codex P1 finding: removing ONE old
    same-identity entry must exempt at most ONE replacement, not an
    unlimited number of new same-named entries."""
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT.replace(
        'dev = ["pytest>=8.0.0"]',
        'dev = ["pytest>=9.0.0", "pytest<10"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_lenient_mode_limits_same_identity_exemption_to_one_removal():
    base = "pytest>=8.0.0\n"
    head = "pytest>=9.0.0\npytest<10\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_tomllib_import_falls_back_to_tomli_on_python_3_10(monkeypatch):
    """Regression for the round-5 Codex P2 finding: pyproject.toml declares
    "requires-python = >=3.10", but stdlib tomllib does not exist before
    3.11. Simulate that by blocking the tomllib import and reloading the
    module, then verify it falls back to importing something named
    'tomli' instead of every pyproject validation permanently raising
    RuntimeError.

    The real 'tomli' backport is only installed via the
    "python_version < 3.11" marker on pyproject.toml/requirements.txt, so
    it is legitimately absent under this repo's own CI (3.12+). Rather than
    depend on that optional package actually being installed, inject a
    minimal stand-in 'tomli' module (backed by the real stdlib tomllib's
    parser) so this test deterministically exercises the fallback-import
    code path in every environment, not just ones with tomli installed.
    """
    import builtins
    import importlib
    import sys
    import types

    import validators.dependency_manifest_diff_validator as validator_module

    real_tomllib = importlib.import_module("tomllib")
    fake_tomli = types.ModuleType("tomli")
    fake_tomli.loads = real_tomllib.loads
    fake_tomli.TOMLDecodeError = real_tomllib.TOMLDecodeError

    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "tomllib":
            raise ModuleNotFoundError("simulated: no module named 'tomllib'")
        if name == "tomli":
            return fake_tomli
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    monkeypatch.setitem(sys.modules, "tomli", fake_tomli)
    try:
        importlib.reload(validator_module)
        assert validator_module.tomllib is fake_tomli
        result = validator_module.validate_pyproject_toml_diff(
            BASE_PYPROJECT, BASE_PYPROJECT, ALLOWED
        )
        assert result.is_valid, result.violations
    finally:
        monkeypatch.undo()
        importlib.reload(validator_module)
        assert validator_module.tomllib.__name__ == "tomllib"


def test_requirements_txt_rejects_extras_on_allowlisted_package():
    """Regression for the round-6 Codex P1 finding: a brand-new addition
    that declares extras on an otherwise-allowlisted package name (e.g.
    "fpdf2[crypto]>=2.7") must be rejected -- extras install additional
    transitive dependencies that were never reviewed through the trust-root
    allowlist, even though "fpdf2" alone is approved."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\nfpdf2[crypto]>=2.7\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("declares extras" in v for v in result.violations)

    strict_result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert not strict_result.is_valid
    assert any("declares extras" in v for v in strict_result.violations)


def test_pyproject_rejects_extras_on_allowlisted_package():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "fpdf2[crypto]>=2.7"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "project.dependencies added entry" in v and "declares extras" in v
        for v in result.violations
    )


def test_requirements_txt_canonicalizes_package_name_case_before_allowlist_check():
    """Regression for the round-6 Codex P2 finding: Python distribution
    names are case-insensitive (PEP 503) and pip resolves "PDFPlumber" to
    the same project as the allowlisted "pdfplumber"; a raw string
    comparison rejected the differently-cased spelling as unapproved."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\nPDFPlumber>=0.10\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations

    strict_result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert strict_result.is_valid, strict_result.violations


def test_pyproject_canonicalizes_package_name_case_before_allowlist_check():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "PDFPlumber>=0.10"]',
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_requirements_txt_unapproved_addition_still_rejected_regardless_of_case():
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\nRequests>=2.31.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_joins_hash_pinned_line_continuation():
    """Regression for the round-6 Codex P2 finding: an approved, pinned
    requirement using pip's standard multiline hash form (a trailing "\\"
    followed by an indented "--hash=..." continuation) is ONE logical
    requirement to pip, not two. Splitting the continuation into a separate
    physical line made it look like an unapproved "package"."""
    base = "pyyaml>=6.0.1\n"
    head = (
        "pyyaml>=6.0.1\n"
        "pdfplumber==0.11.0 \\\n"
        "    --hash=sha256:"
        + "0" * 64
        + "\n"
    )
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations

    strict_result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert strict_result.is_valid, strict_result.violations


def test_requirements_txt_hash_continuation_of_unapproved_package_still_fails():
    """The continuation-join must not become a bypass: an unapproved
    package split across a hash continuation is still rejected as a single
    joined, unapproved requirement."""
    base = "pyyaml>=6.0.1\n"
    head = (
        "pyyaml>=6.0.1\n"
        "requests==2.31.0 \\\n"
        "    --hash=sha256:"
        + "0" * 64
        + "\n"
    )
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_requirements_txt_hash_continuation_unchanged_does_not_fail_strict_mode():
    """A hash-pinned continuation that survives unchanged from base to head
    must not be misread as a removed-then-different logical line."""
    text = (
        "pdfplumber==0.11.0 \\\n"
        "    --hash=sha256:"
        + "0" * 64
        + "\n"
    )
    result = validate_requirements_txt_diff(text, text, ALLOWED)
    assert result.is_valid, result.violations


def test_pyproject_dependency_groups_rejects_unapproved_addition_in_lenient_mode():
    """Regression for the round-7 Codex P1 finding: PEP 735
    [dependency-groups] entries are installed via "pip install --group
    <name>" but were never inspected at all, so an unapproved addition to a
    brand-new group passed lenient (CI-wide) validation."""
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["unapproved-package>=1"]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "dependency-groups" in v and "not an approved addition" in v
        for v in result.violations
    )

    strict_result = validate_pyproject_toml_diff(base, head, ALLOWED)
    assert not strict_result.is_valid


def test_pyproject_dependency_groups_allows_approved_addition():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["pdfplumber>=0.10"]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_pyproject_dependency_groups_rejects_direct_url_even_if_name_allowed():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["pdfplumber @ https://attacker.invalid/pkg.whl"]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("direct URL/source reference" in v for v in result.violations)


def test_pyproject_dependency_groups_rejects_extras_on_allowlisted_package():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["fpdf2[crypto]>=2.7"]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("declares extras" in v for v in result.violations)


def test_pyproject_dependency_groups_include_group_reference_to_existing_group_passes():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["pdfplumber>=0.10"]\n'
        'all = [{include-group = "docs"}]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_pyproject_dependency_groups_include_group_reference_to_missing_group_fails():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'all = [{include-group = "nonexistent"}]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("include-group" in v and "nonexistent" in v for v in result.violations)


def test_pyproject_dependency_groups_unrecognized_entry_shape_fails_closed():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = [{unexpected-key = "whatever"}]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not a recognized PEP 735 form" in v for v in result.violations)


def test_pyproject_dependency_groups_existing_group_survives_strict_mode():
    base = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'docs = ["pdfplumber>=0.10"]\n'
    )
    result = validate_pyproject_toml_diff(base, base, ALLOWED)
    assert result.is_valid, result.violations


def test_pyproject_dependency_groups_repointing_include_group_to_unapproved_group_fails():
    """Regression for the round-8 Codex P1 finding: an include-group entry
    that starts pointing at a DIFFERENT, already-existing-but-unapproved
    group must still be rejected, even though neither group's own direct
    entries changed -- what "pip install --group all" resolves to did
    change, because the resolved closure (not just direct entries) is what
    matters."""
    base = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'safe = ["pdfplumber>=0.10"]\n'
        'legacy = ["unapproved-package>=1"]\n'
        'all = [{include-group = "safe"}]\n'
    )
    head = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'safe = ["pdfplumber>=0.10"]\n'
        'legacy = ["unapproved-package>=1"]\n'
        'all = [{include-group = "legacy"}]\n'
    )
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any(
        "dependency-groups" in v and "not an approved addition" in v
        for v in result.violations
    )


def test_pyproject_dependency_groups_transitive_include_resolves_nested_group():
    """A group that includes a group which itself includes a THIRD group
    must surface the third group's entries too."""
    base = BASE_PYPROJECT + (
        "\n[dependency-groups]\n"
        'leaf = ["pdfplumber>=0.10"]\n'
        'mid = [{include-group = "leaf"}]\n'
        'top = [{include-group = "mid"}]\n'
    )
    result = validate_pyproject_toml_diff(base, base, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations

    head = base.replace('leaf = ["pdfplumber>=0.10"]', 'leaf = ["unapproved-package>=1"]')
    result = validate_pyproject_toml_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("not an approved addition" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_build_backend_change():
    """Regression for the round-8 Codex P1 finding: changing which build
    backend is used (or where an in-tree backend's source is loaded from)
    can introduce additional, unreviewed requirements via the backend's own
    hooks (e.g. get_requires_for_build_wheel()) that this validator cannot
    inspect, even though build-system.requires itself stays untouched."""
    base_with_build_system = (
        BASE_PYPROJECT
        + '\n[build-system]\nrequires = ["setuptools>=61.0"]\n'
        'build-backend = "setuptools.build_meta"\n'
    )
    head = base_with_build_system.replace(
        'build-backend = "setuptools.build_meta"',
        'build-backend = "_custom_backend"\nbackend-path = ["."]',
    )
    result = validate_pyproject_toml_diff(
        base_with_build_system, head, ALLOWED, strict_additive_only=False
    )
    assert not result.is_valid
    assert any("build-backend/backend-path changed" in v for v in result.violations)

    strict_result = validate_pyproject_toml_diff(base_with_build_system, head, ALLOWED)
    assert not strict_result.is_valid


def test_pyproject_unchanged_build_backend_does_not_fail():
    base_with_build_system = (
        BASE_PYPROJECT
        + '\n[build-system]\nrequires = ["setuptools>=61.0"]\n'
        'build-backend = "setuptools.build_meta"\n'
    )
    result = validate_pyproject_toml_diff(
        base_with_build_system, base_with_build_system, ALLOWED, strict_additive_only=False
    )
    assert result.is_valid, result.violations


def test_requirements_txt_lenient_mode_rejects_spaced_extras_replacement():
    """Regression for the round-8 Codex P1 finding: PEP 508 permits
    whitespace before the extras marker ("pydantic [email]>=2.6"). Without
    accounting for that whitespace, this replacement's identity was
    indistinguishable from the plain "pydantic>=2.5.0" it replaced, so the
    lenient-mode same-identity exemption incorrectly let the extras-adding
    change through without allowlist review."""
    base = "pydantic>=2.5.0\n"
    head = "pydantic [email]>=2.6.0\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("declares extras" in v for v in result.violations)


def test_pyproject_lenient_mode_rejects_spaced_extras_replacement():
    base = BASE_PYPROJECT
    head = BASE_PYPROJECT.replace(
        'dependencies = ["pyyaml>=6.0.1"]',
        'dependencies = ["pyyaml>=6.0.1", "pydantic>=2.5.0"]',
    )
    head_with_extras = head.replace(
        '"pydantic>=2.5.0"', '"pydantic [email]>=2.6.0"'
    )
    # Establish "pydantic>=2.5.0" as an existing base entry first, then
    # replace it with the spaced-extras form.
    base_with_pydantic = head
    result = validate_pyproject_toml_diff(
        base_with_pydantic, head_with_extras, ALLOWED, strict_additive_only=False
    )
    assert not result.is_valid
    assert any(
        "project.dependencies added entry" in v and "declares extras" in v
        for v in result.violations
    )


def test_requirements_txt_inline_comment_on_approved_addition_passes():
    """Regression for the round-8 Codex P2 finding: pip discards an inline
    comment (e.g. "pdfplumber>=0.10  # docs https://example.com") and
    installs the plain requirement, but a URL inside that comment was
    previously misread by the direct-reference/VCS scan as an unapproved
    source, rejecting an ordinary, already-approved addition."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\npdfplumber>=0.10  # docs https://example.com\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert result.is_valid, result.violations


def test_requirements_txt_inline_comment_does_not_mask_a_real_url_addition():
    """The inline-comment strip must not become a bypass: an added line
    that is genuinely a direct URL reference (not merely commented) is
    still rejected."""
    base = "pyyaml>=6.0.1\n"
    head = "pyyaml>=6.0.1\npdfplumber @ https://attacker.invalid/pkg.whl  # totally fine\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED, strict_additive_only=False)
    assert not result.is_valid
    assert any("direct URL/source reference" in v for v in result.violations)


def test_requirements_txt_inline_comment_change_only_does_not_fail_strict_mode():
    """A line whose install-time content is unchanged but whose trailing
    comment text changed is not a manifest modification."""
    base = "pyyaml>=6.0.1  # old note\n"
    head = "pyyaml>=6.0.1  # updated note\n"
    result = validate_requirements_txt_diff(base, head, ALLOWED)
    assert result.is_valid, result.violations


