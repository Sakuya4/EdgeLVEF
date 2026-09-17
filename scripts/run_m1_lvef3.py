from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edgelvef.application.analyze_lvid_cine import analyze_lvid_cine  # noqa: E402
from edgelvef.infrastructure.calibration_config import load_monotonic_calibration  # noqa: E402
from edgelvef.infrastructure.onnx_lvid_tracker import OnnxLvidTracker  # noqa: E402
from edgelvef.infrastructure.video import crop_frames, load_grayscale_cine  # noqa: E402


MODEL_SHA256 = "CC95301A37A131F3926EA85A2FAB7A86DDED13C5DD2501F21FEEAB4D213C6B42"


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(item) for item in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Crop must be x1,y1,x2,y2")
    return parts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run interpretable M1-LVEF3 on one PLAX cine")
    parser.add_argument("cine", type=Path)
    parser.add_argument("--fps", type=float, default=50.0)
    parser.add_argument("--crop", type=parse_crop)
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "m1_lvef3" / "m1_lvid_tracker_fp32.onnx",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=ROOT / "models" / "m1_lvef3" / "balanced_calibration.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frames = crop_frames(load_grayscale_cine(args.cine), args.crop)
    tracker = OnnxLvidTracker(
        args.model,
        provider=args.provider,
        expected_sha256=MODEL_SHA256,
    )
    calibration = load_monotonic_calibration(args.calibration)
    result = analyze_lvid_cine(frames, args.fps, tracker, calibration).to_dict()
    result["cine"] = str(args.cine)
    result["fps"] = args.fps
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
