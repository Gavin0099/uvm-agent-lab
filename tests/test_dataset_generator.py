import pytest
from dataset_gen.sft_generator import UVMDatasetSFTGenerator
from dataset_gen.dpo_generator import UVMDatasetDPOGenerator


def test_sft_dataset_generation():
    gen = UVMDatasetSFTGenerator()
    records = gen.generate_sft_records()

    assert len(records) >= 10
    for r in records:
        assert "case_id" in r
        assert "requirement_id" in r
        assert len(r["messages"]) == 3
        assert r["messages"][0]["role"] == "system"
        assert r["messages"][1]["role"] == "user"
        assert r["messages"][2]["role"] == "assistant"
        assert len(r["messages"][2]["content"]) > 20


def test_dpo_dataset_generation_and_preference_separation():
    gen = UVMDatasetDPOGenerator()
    records = gen.generate_dpo_records()

    assert len(records) >= 10
    for r in records:
        assert "prompt" in r
        assert "chosen" in r
        assert "rejected" in r
        assert r["chosen"] != r["rejected"]
        # Chosen should contain valid UVM, rejected should contain violation markers
        assert "uvm" in r["chosen"].lower()
        assert "VIOLATION" in r["rejected"] or "rtl" in r["rejected"].lower()
