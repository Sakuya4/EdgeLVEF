from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...infrastructure.benchmark import benchmark_onnx, system_record
from .analyze import MODEL_SHA256, REPOSITORY_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the frozen Student Model on an execution target")
    parser.add_argument("--model", type=Path, default=REPOSITORY_ROOT / "models/student_model/student_model_fp32.onnx")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--claim-physical-target", action="store_true")
    args = parser.parse_args()
    result = {
        **system_record(args.target_name, args.claim_physical_target),
        **benchmark_onnx(args.model, args.provider, args.warmup, args.runs),
    }
    result["checksum_passed"] = result["model_sha256"] == MODEL_SHA256
    if not result["checksum_passed"]:
        raise RuntimeError(f"Frozen model checksum mismatch: {result['model_sha256']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
