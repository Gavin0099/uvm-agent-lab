from typing import Dict, Any, List


class DualGV100VRAMTracker:
    """
    VRAM & KV Cache Budget Tracker for Dual NVIDIA GV100 (32GB x 2 = 64GB Aggregate VRAM).
    """

    TOTAL_VRAM_PER_GPU_GB = 32.0
    TOTAL_VRAM_AGGREGATE_GB = 64.0

    MODEL_SPECS = {
        "Qwen/Qwen3.8-35B-A3B": {
            "params_b": 35.0,
            "hidden_size": 5120,
            "num_layers": 64,
            "num_kv_heads": 8,
            "head_dim": 128
        },
        "Qwen/Qwen3.8-27B": {
            "params_b": 27.0,
            "hidden_size": 4096,
            "num_layers": 48,
            "num_kv_heads": 8,
            "head_dim": 128
        }
    }

    BYTES_PER_PARAM = {
        "FP16": 2.0,
        "FP8": 1.0,
        "Q8_0": 1.1,
        "Q4_K_M": 0.55,
        "AWQ_4BIT": 0.55,
        "GPTQ_4BIT": 0.55
    }

    KV_BYTES_PER_VALUE = {
        "FP16": 2.0,
        "Q8_0": 1.1,
        "Q4_0": 0.55,
        "Q4_1": 0.55,
        "Q5_0": 0.7,
        "Q5_1": 0.7,
    }

    @classmethod
    def estimate_memory_budget(
        cls,
        model_name: str,
        quantization: str,
        context_length: int,
        tensor_parallel: int = 2,
        kv_cache_type: str = "FP16",
    ) -> Dict[str, Any]:
        spec = cls.MODEL_SPECS.get(model_name, cls.MODEL_SPECS["Qwen/Qwen3.8-35B-A3B"])
        bytes_per_p = cls.BYTES_PER_PARAM.get(quantization, 0.55)

        # 1. Weights memory (GB)
        weight_mem_gb = (spec["params_b"] * 1e9 * bytes_per_p) / (1024 ** 3)
        weight_per_gpu = weight_mem_gb / tensor_parallel

        kv_bytes_per_value = cls.KV_BYTES_PER_VALUE.get(kv_cache_type.upper(), 2.0)
        # 2. KV Cache per token per layer = K/V x heads x head_dim x dtype bytes.
        kv_bytes_per_token = 2 * spec["num_kv_heads"] * spec["head_dim"] * spec["num_layers"] * kv_bytes_per_value
        total_kv_gb = (kv_bytes_per_token * context_length) / (1024 ** 3)
        kv_per_gpu = total_kv_gb / tensor_parallel

        # 3. CUDA overhead & Activation buffer (approx 2GB per GPU)
        overhead_per_gpu = 2.0

        peak_per_gpu = weight_per_gpu + kv_per_gpu + overhead_per_gpu
        is_feasible = peak_per_gpu <= cls.TOTAL_VRAM_PER_GPU_GB

        return {
            "model_name": model_name,
            "quantization": quantization,
            "context_length": context_length,
            "tensor_parallel": tensor_parallel,
            "kv_cache_type": kv_cache_type,
            "weight_memory_total_gb": round(weight_mem_gb, 2),
            "kv_cache_total_gb": round(total_kv_gb, 2),
            "peak_vram_per_gpu_gb": round(peak_per_gpu, 2),
            "vram_limit_per_gpu_gb": cls.TOTAL_VRAM_PER_GPU_GB,
            "is_feasible": is_feasible,
            "recommendation": "FEASIBLE" if is_feasible else "OOM_RISK_REDUCE_CONTEXT_OR_QUANTIZE"
        }
