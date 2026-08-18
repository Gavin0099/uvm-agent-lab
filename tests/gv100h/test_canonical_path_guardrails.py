import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.policy import GovernanceViolationCode


def test_canonical_path_normal_access():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        (tmp_path / "rtl").mkdir(parents=True)
        
        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        
        # Legitimate access
        passed, report = guardrail.check_path_access("uvm/tests/my_test.sv")
        assert passed is True
        assert report.passed is True


def test_canonical_path_traversal_into_forbidden():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        (tmp_path / "rtl").mkdir(parents=True)
        
        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        
        # Traversal attempt: starts with uvm/tests/ but traverses into rtl/
        passed, report = guardrail.check_path_access("uvm/tests/../../rtl/core.sv")
        assert passed is False
        assert report.fatal is True
        assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH


def test_canonical_path_windows_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        (tmp_path / "rtl").mkdir(parents=True)
        
        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        
        # Windows backslash traversal
        passed, report = guardrail.check_path_access("uvm\\tests\\..\\..\\rtl\\core.sv")
        assert passed is False
        assert report.fatal is True
        assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH


def test_canonical_path_escape_outside_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        
        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        
        # Traversal out of repo root entirely
        passed, report = guardrail.check_path_access("../../etc/passwd")
        assert passed is False
        assert report.fatal is True
        assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS


def test_canonical_path_case_insensitivity():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        (tmp_path / "rtl").mkdir(parents=True)
        
        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        
        # Case variation on forbidden path
        passed, report = guardrail.check_path_access("RTL/core.sv")
        assert passed is False
        assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH

        # Case variation on allowed path
        passed_allowed, report_allowed = guardrail.check_path_access("UVM/Tests/my_test.sv")
        assert passed_allowed is True
