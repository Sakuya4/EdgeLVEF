from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...infrastructure.onnx_wall_model import OnnxWallModel
from ...infrastructure.overlay import render_wall_overlay
from ...infrastructure.video import crop_frames, load_grayscale_cine
from .analyze import MODEL_SHA256, REPOSITORY_ROOT, parse_crop


def main() -> None:
    parser = argparse.ArgumentParser(description="Render blinded two-wall and ED/ES overlays")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", type=Path, default=REPOSITORY_ROOT / "models/student_model/student_model_fp32.onnx")
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--crop", type=parse_crop)
    parser.add_argument("--fps", type=float, default=15.0)
    args = parser.parse_args()
    frames = crop_frames(load_grayscale_cine(args.input), args.crop)
    model = OnnxWallModel(args.model, args.provider, MODEL_SHA256)
    result = render_wall_overlay(frames, model.predict(frames), args.output, args.fps)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
