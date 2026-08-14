# Gate 4: GV100 Hardware & Parallelism Characterization

## Objective
Profile local inference throughput, memory consumption, context window scaling (32k/64k/128k), and NVLink tensor parallelism (TP=1 vs TP=2) on dual Tesla GV100 GPUs.

## Tracked Metrics
- Peak VRAM Allocation
- Time-to-First-Token (TTFT)
- Generation Speed (tokens/sec)
- Interconnect scaling efficiency ($Speedup_{TP=2} / 2.0$)
