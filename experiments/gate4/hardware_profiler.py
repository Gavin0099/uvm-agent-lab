import math
from typing import Dict, Any, List


class HardwareProfiler:
    """
    Gate 4: Hardware Profiling & KV Cache Memory Calculator.
    Specifically profiles dual NVIDIA Tesla/Quadro GV100 (32GB HBM2 each, 64GB total VRAM).
    """

    GPU_CONFIGS = {
        "dual_gv100_nvlink": {
            "num_gpus": 2,
            "vram_per_gpu_gb": 32.0,
            "total_vram_gb": 64.0,
            "memory_bandwidth_gb_s": 870.0,
            "nvlink_bandwidth_gb_s": 200.0,
            "interconnect": "NVLink 2.0 Bridge",
        }
    }

    MODEL_SPECS = {
        "Qwen-2.5-Coder-32B": {
            "params_billion": 32.5,
            "num_layers": 64,
            "hidden_size": 5120,
            "num_attention_heads": 40,
            "num_kv_heads": 8,  # GQA
            "head_dim": 128,
            "vocab_size": 152064,
        },
        "Nemotron-4-15B": {
            "params_billion": 15.0,
            "num_layers": 40,
            "hidden_size": 4096,
            "num_attention_heads": 32,
            "num_kv_heads": 8,
            "head_dim": 128,
            "vocab_size": 128000,
        },
        "DeepSeek-Coder-V2-Lite": {
            "params_billion": 15.7,
            "active_params_billion": 2.4,
            "num_layers": 28,
            "hidden_size": 2048,
            "num_attention_heads": 16,
            "num_kv_heads": 16,
            "head_dim": 128,
            "vocab_size": 102400,
        }
    }

    @staticmethod
    def calculate_vram_requirement(
        model_name: str,
        context_length: int,
        precision_mode: str = "AWQ_4BIT",  # "AWQ_4BIT", "INT8", "FP16"
        batch_size: int = 1,
        tensor_parallel: int = 2,
    ) -> Dict[str, Any]:
        spec = HardwareProfiler.MODEL_SPECS.get(model_name)
        if not spec:
            raise ValueError(f"Unknown model spec '{model_name}'")

        if precision_mode == "AWQ_4BIT":
            bytes_per_weight = 0.55  # 4-bit plus scale/zero-point overhead
            kv_bytes = 2.0          # FP16 KV Cache
        elif precision_mode == "INT8":
            bytes_per_weight = 1.0
            kv_bytes = 2.0
        else:  # FP16
            bytes_per_weight = 2.0
            kv_bytes = 2.0

        # 1. Weights Memory
        weight_vram_gb = (spec["params_billion"] * bytes_per_weight)
        vram_weights_per_gpu = weight_vram_gb / tensor_parallel

        # 2. KV Cache Memory (GQA): 2 * layers * kv_heads * head_dim * kv_bytes * context_length * batch_size
        kv_bytes_per_token = 2 * spec["num_layers"] * spec["num_kv_heads"] * spec["head_dim"] * kv_bytes
        total_kv_vram_gb = (kv_bytes_per_token * context_length * batch_size) / (1024 ** 3)
        vram_kv_per_gpu = total_kv_vram_gb / tensor_parallel

        # 3. Activation & System Overhead (CUDA runtime context ~ 1.5 GB)
        cuda_overhead_gb = 1.5
        total_vram_per_gpu = vram_weights_per_gpu + vram_kv_per_gpu + cuda_overhead_gb

        gpu_capacity = 32.0  # GV100
        fits_in_gpu = total_vram_per_gpu <= gpu_capacity
        headroom_gb = gpu_capacity - total_vram_per_gpu

        # 4. Latency & Throughput Estimation
        est_ttft_ms = (context_length * weight_vram_gb * 1024) / (870.0 * 1000) * 1000
        est_tok_per_sec = (870.0 / max(1.0, (weight_vram_gb / tensor_parallel))) * 0.45

        return {
            "model_name": model_name,
            "context_length": context_length,
            "precision": precision_mode,
            "tensor_parallel": tensor_parallel,
            "weights_vram_per_gpu_gb": round(vram_weights_per_gpu, 2),
            "kv_cache_vram_per_gpu_gb": round(vram_kv_per_gpu, 2),
            "total_vram_per_gpu_gb": round(total_vram_per_gpu, 2),
            "gpu_capacity_gb": gpu_capacity,
            "fits_in_memory": fits_in_gpu,
            "headroom_gb": round(headroom_gb, 2),
            "est_ttft_ms": round(max(45.0, est_ttft_ms), 1),
            "est_tokens_per_sec": round(min(85.0, max(15.0, est_tok_per_sec)), 1),
        }
