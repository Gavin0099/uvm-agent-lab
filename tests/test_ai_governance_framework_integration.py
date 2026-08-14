import pytest
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAMEWORK_ROOT = PROJECT_ROOT / "additional" / "ai-governance-framework"


def test_governance_drift_checker_clean():
    """Verify that governance_drift_checker returns ok=True and severity=ok."""
    if not FRAMEWORK_ROOT.exists():
        pytest.skip("Submodule additional/ai-governance-framework not checked out.")

    cmd = [
        sys.executable,
        str(FRAMEWORK_ROOT / "governance_tools" / "governance_drift_checker.py"),
        "--repo", str(PROJECT_ROOT),
        "--framework-root", str(FRAMEWORK_ROOT)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    assert res.returncode == 0
    assert "ok                 = True" in res.stdout
    assert "severity           = ok" in res.stdout


def test_governance_quickstart_smoke():
    """Verify that quickstart_smoke returns ok=True."""
    if not FRAMEWORK_ROOT.exists():
        pytest.skip("Submodule additional/ai-governance-framework not checked out.")

    cmd = [
        sys.executable,
        str(FRAMEWORK_ROOT / "governance_tools" / "quickstart_smoke.py"),
        "--project-root", str(PROJECT_ROOT),
        "--plan", "PLAN.md",
        "--contract", "contract.yaml",
        "--format", "human"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    assert res.returncode == 0
    assert "ok=True" in res.stdout
