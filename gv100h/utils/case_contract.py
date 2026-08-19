import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def canonical_case_bytes(case_data: Dict[str, Any]) -> bytes:
    return json.dumps(
        case_data,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_benchmark_case_hash(case_data: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_case_bytes(case_data)).hexdigest()


def load_benchmark_case(repo_root: Path, task_id: str) -> Dict[str, Any]:
    cases_dir = Path(repo_root).resolve() / "benchmarks" / "cases"
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"Benchmark case registry not found: {cases_dir}")

    candidates = sorted(cases_dir.glob("*.yaml"))
    matches = []
    for case_path in candidates:
        with open(case_path, "r", encoding="utf-8") as handle:
            case_data = yaml.safe_load(handle)
        if isinstance(case_data, dict) and case_data.get("id") == task_id:
            matches.append((case_path, case_data))

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one canonical benchmark case for {task_id!r}, found {len(matches)}"
        )
    return matches[0][1]


def resolve_benchmark_case(
    repo_root: Path,
    task_id: str,
    claimed_hash: Optional[str],
) -> Dict[str, Any]:
    if not claimed_hash:
        raise ValueError("benchmark_case_hash is required for trusted case binding")
    case_data = load_benchmark_case(repo_root, task_id)
    actual_hash = compute_benchmark_case_hash(case_data)
    if claimed_hash != actual_hash:
        raise ValueError(
            "benchmark_case_hash does not match the trusted case registry"
        )
    return case_data
