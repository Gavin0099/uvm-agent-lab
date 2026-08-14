import pytest
from agent.coverage.coverage_parser import FunctionalCoverageParser
from agent.coverage.directed_seq_generator import DirectedSequenceGenerator
from agent.coverage.closure_loop import AutomatedCoverageClosureLoop


def test_coverage_parser_identifies_unhit_bins():
    report = """
    Coverage Summary Report:
    bin cp_reset_idle : count = 15 [HIT]
    bin cp_warm_reset_12cyc : count = 0 [UNHIT]
    bin cp_tready_backpressure_min : hits = 0
    bin cp_tready_backpressure_max : hits = 42
    """
    parsed = FunctionalCoverageParser.parse_report(report)
    assert parsed["total_bins"] == 4
    assert parsed["hit_bins"] == 2
    assert parsed["coverage_percentage"] == 50.0
    assert "cp_warm_reset_12cyc" in parsed["unhit_bins"]
    assert "cp_tready_backpressure_min" in parsed["unhit_bins"]


def test_directed_sequence_generator():
    unhit = ["cp_warm_reset_12cyc", "cp_tready_backpressure_min"]
    seq = DirectedSequenceGenerator.generate_directed_sequence(unhit)
    
    assert "directed_closure_seq" in seq["sequence_name"]
    assert "constraint" in seq["code"]
    assert len(seq["targeted_bins"]) == 2


def test_automated_closure_loop():
    initial_report = """
    bin b1 [UNHIT]
    bin b2 [UNHIT]
    bin b3 [HIT]
    """
    loop = AutomatedCoverageClosureLoop(target_coverage=100.0, max_iterations=4)
    result = loop.run_closure_loop(initial_report)
    
    assert result["status"] == "closed"
    assert result["final_coverage"] == 100.0
    assert result["iterations_taken"] >= 1
