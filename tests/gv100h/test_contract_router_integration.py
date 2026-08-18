import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from gv100h.governance.contract_router import TaskContractRouter


def test_contract_router_loads_tasks():
    router = TaskContractRouter()
    tasks = router.list_tasks()
    assert "GV100H-M-1-BOOTSTRAP" in tasks
    assert "GV100H-M-1B" in tasks
    assert "GV100H-M0" in tasks
    assert "GV100H-M1" in tasks
    assert "GV100H-M2" in tasks
    assert "GV100H-M3" in tasks
    assert "GV100H-M4" in tasks


def test_contract_router_get_task_contract_explicit():
    router = TaskContractRouter()
    contract = router.get_task_contract("GV100H-M-1-BOOTSTRAP")
    assert contract["task_id"] == "GV100H-M-1-BOOTSTRAP"
    assert "gv100h/governance/" in contract["allowed_paths"]
    assert "rtl/" in contract["forbidden_paths"]


def test_contract_router_env_var_binding(monkeypatch):
    monkeypatch.setenv("GV100H_TASK_ID", "GV100H-M0")
    router = TaskContractRouter()
    contract = router.get_task_contract()
    assert contract["task_id"] == "GV100H-M0"
    assert "gv100h/schemas/" in contract["allowed_paths"]


def test_contract_router_invalid_task_raises():
    router = TaskContractRouter()
    with pytest.raises(KeyError):
        router.get_task_contract("INVALID_TASK_NAME")


def test_contract_router_creates_guardrail():
    router = TaskContractRouter()
    guardrail = router.create_guardrail_for_task("GV100H-M-1-BOOTSTRAP")
    
    # Allowed in bootstrap
    passed, report = guardrail.check_path_access("gv100h/governance/contract_router.py")
    assert passed is True
    assert report.passed is True
    
    # Forbidden RTL
    passed_rtl, report_rtl = guardrail.check_path_access("rtl/usb3_ctrl.sv")
    assert passed_rtl is False
    assert report_rtl.fatal is True
