from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edgelvef.infrastructure.onnx_m1_measurement_model import (  # noqa: E402
    MEASUREMENT_CHANNELS,
    OnnxM1MeasurementModel,
)


MODEL_SHA256 = "B9CBB77DB1D9762802074D8750968D9CEC7C97C8472C046EEFE160F139695B50"
COLORS = {
    "IVSd": (255, 255, 255),
    "LVIDd": (0, 255, 0),
    "LVIDs": (0, 200, 255),
    "LVPWd": (255, 180, 0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen M1-A endpoint baseline on one cine frame.")
    parser.add_argument("cine", type=Path)
    parser.add_argument("--frame", type=int, help="Center frame; defaults to the middle frame")
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "m1_measurement_baseline" / "m1_measurement_fp32.onnx",
    )
    parser.add_argument("--overlay", type=Path, help="Optional annotated PNG output")
    return parser.parse_args()


def read_cine(path: Path) -> np.ndarray:
    capture = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()
    if not frames:
        raise ValueError(f"Cannot decode cine: {path}")
    return np.stack(frames)


def main() -> None:
    args = parse_args()
    frames = read_cine(args.cine)
    center = args.frame if args.frame is not None else len(frames) // 2
    model = OnnxM1MeasurementModel(args.model, expected_sha256=MODEL_SHA256)
    result = model.predict(frames, [center])[0]
    result["cine"] = str(args.cine)
    result["note"] = "Image-space research output; physical units and ED/ES phase are not inferred."
    if args.overlay is not None:
        canvas = cv2.cvtColor(cv2.resize(frames[center], (256, 256)), cv2.COLOR_GRAY2BGR)
        for name in MEASUREMENT_CHANNELS:
            endpoints = np.round(result["measurements"][name]["endpoints_xy_256"]).astype(int)
            cv2.line(canvas, tuple(endpoints[0]), tuple(endpoints[1]), COLORS[name], 2, cv2.LINE_AA)
            cv2.putText(
                canvas,
                name,
                tuple(endpoints[0]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                COLORS[name],
                1,
                cv2.LINE_AA,
            )
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.overlay), canvas)
        result["overlay"] = str(args.overlay)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
