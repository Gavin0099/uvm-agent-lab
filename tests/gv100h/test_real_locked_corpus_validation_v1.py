from pathlib import Path

from scripts.validate_real_locked_corpus_v1 import (
    DEFAULT_MANIFEST_PATH,
    run_validation,
)


def test_validation_reports_not_run_without_locked_raw_corpus(tmp_path):
    result = run_validation(
        raw_root=tmp_path / "missing-locked-corpus",
        manifest_path=DEFAULT_MANIFEST_PATH,
    )

    assert result["status"] == "NOT_RUN"
    assert "official locked raw corpus" in result["reason"]
    assert result["baseline_evidence"]["table_6_30_value_rank_q02"] == 2813