import pytest
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_poc_report import generate_report


@pytest.mark.contract
def test_qualification_policy_loading():
    policy_file = PROJECT_ROOT / "gv100h" / "qualification" / "qualification_policy.yaml"
    assert policy_file.exists()
    
    with open(policy_file, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    
    assert "policy_gates" in policy
    assert policy["policy_gates"]["spec_qa"]["max_fabricated_citations"] == 0
    assert "GO" in policy["decision_rules"]


@pytest.mark.contract
def test_generate_poc_report_execution():
    report_text = generate_report()
    assert "# GV100H Local AI Agent POC 資格評審報告" in report_text
    assert "**`NO_GO — synthetic/offline scaffold only`**" in report_text
    assert "Q1 — Model Quality" in report_text
    assert "Q5 — Governance" in report_text
    assert "808f23c24bd8651da9cdcd63ea8669126917a379" in report_text
