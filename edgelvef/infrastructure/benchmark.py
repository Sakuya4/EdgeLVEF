from __future__ import annotations

import hashlib
import os
import platform
import statistics
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

try:
    import resource
except ImportError:
    resource = None


def benchmark_onnx(
    model_path: Path,
    provider: str,
    warmup: int,
    runs: int,
) -> dict[str, object]:
    if provider not in ort.get_available_providers():
        raise ValueError(f"Unavailable ONNX Runtime provider: {provider}")
    session = ort.InferenceSession(str(model_path), providers=[provider])
    input_meta = session.get_inputs()[0]
    shape = [1 if not isinstance(value, int) else value for value in input_meta.shape]
    tensor = np.random.default_rng(20260821).normal(size=shape).astype(np.float32)
    for _ in range(warmup):
        session.run(None, {input_meta.name: tensor})
    elapsed = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        output = session.run(None, {input_meta.name: tensor})
        elapsed.append((time.perf_counter_ns() - start) / 1e6)
    return {
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest().upper(),
        "provider_requested": provider,
        "providers_active": session.get_providers(),
        "warmup": warmup,
        "runs": runs,
        "median_ms": statistics.median(elapsed),
        "p95_ms": float(np.quantile(elapsed, 0.95)),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
        "output_shapes": [list(value.shape) for value in output],
        "finite_outputs": all(np.isfinite(value).all() for value in output),
    }


def system_record(target_name: str, physical_target_claimed: bool) -> dict[str, object]:
    if physical_target_claimed and platform.system() != "Linux":
        raise RuntimeError("Physical Embedded Linux claims require execution on Linux")
    os_release_path = Path("/etc/os-release")
    return {
        "target_name": target_name,
        "physical_target_claimed": physical_target_claimed,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "os_release": os_release_path.read_text(encoding="utf-8", errors="replace") if os_release_path.exists() else None,
        "scope": "Student Model forward only; excludes decode, tracking, and LVEF head",
    }
