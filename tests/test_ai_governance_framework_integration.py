import pytest
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAMEWORK_ROOT = PROJECT_ROOT / "additional" / "ai-governance-framework"


def test_governance_drift_checker_clean():
    """Verify that governance_drift_checker returns ok=True when available."""
    tool_path = FRAMEWORK_ROOT / "governance_tools" / "governance_drift_checker.py"
    if not tool_path.exists():
        pytest.skip(f"Governance drift checker tool not found at {tool_path}.")

    cmd = [
        sys.executable,
        str(tool_path),
        "--repo", str(PROJECT_ROOT),
        "--framework-root", str(FRAMEWORK_ROOT)
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    assert res.returncode == 0
    assert "ok                 = True" in res.stdout
    assert "severity           = ok" in res.stdout


def test_governance_quickstart_smoke():
    """Verify that quickstart_smoke returns ok=True when available."""
    tool_path = FRAMEWORK_ROOT / "governance_tools" / "quickstart_smoke.py"
    if not tool_path.exists():
        pytest.skip(f"Governance quickstart tool not found at {tool_path}.")

    cmd = [
        sys.executable,
        str(tool_path),
        "--project-root", str(PROJECT_ROOT),
        "--plan", "PLAN.md",
        "--contract", "contract.yaml",
        "--format", "human"
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    assert res.returncode == 0
    assert "ok=True" in res.stdout
