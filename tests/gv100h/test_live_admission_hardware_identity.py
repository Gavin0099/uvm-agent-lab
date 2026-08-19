from gv100h.coding_eval.governance_ab_runner import GovernanceABRunner
from gv100h.manifests.models import HardwareManifest
from tests.gv100h.test_m3_coding_eval import _dict_only_pair_manifests


def test_live_admission_rejects_non_v100_gpu():
    base_manifest = _dict_only_pair_manifests()[0]
    manifest = base_manifest.model_copy(update={
        "runtime": "vllm",
        "model_hash": "a" * 64,
        "runtime_commit": "r" * 40,
        "hardware": HardwareManifest(
            gpu_count=1,
            gpu_model="NVIDIA RTX 4090",
            hardware_observed=True,
            vram_total_gb=24.0,
        ),
        "evidence": base_manifest.evidence.model_copy(update={
            "evidence_schema_version": "2",
            "endpoint_observed": True,
            "eda_backend": "vcs",
            "verification_level": "full_uvm_regression",
            "qualification_admissible": True,
        }),
    })

    assert GovernanceABRunner._has_live_qualification_evidence(manifest) is False