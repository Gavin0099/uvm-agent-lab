import pytest
from scripts.eda.router import EDARouter
from scripts.eda.verilator_adapter import VerilatorAdapter
from scripts.eda.iverilog_adapter import IcarusVerilogAdapter
from scripts.eda.vcs_adapter import SynopsysVCSAdapter


def test_eda_router_default_fallback():
    router = EDARouter(preferred_backend="stub")
    assert router.get_active_backend() == "stub"
    
    comp = router.compile(["fixtures/rtl/usb3_ctrl.sv"])
    assert comp["status"] == "pass"
    assert comp["log_hash"] is not None

    sim = router.simulate("usb3_warm_reset_test")
    assert sim["status"] == "pass"
    assert sim["coverage"] == 100.0


def test_eda_adapters_availability_check():
    vcs = SynopsysVCSAdapter()
    verilator = VerilatorAdapter()
    iverilog = IcarusVerilogAdapter()

    # Adapters gracefully report status without throwing exceptions
    assert isinstance(vcs.is_available(), bool)
    assert isinstance(verilator.is_available(), bool)
    assert isinstance(iverilog.is_available(), bool)
