from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...application.analyze_cine import analyze_cine
from ...infrastructure.head_config import load_frozen_head
from ...infrastructure.onnx_wall_model import OnnxWallModel
from ...infrastructure.video import crop_frames, load_grayscale_cine


MODEL_SHA256 = "FE5FC82B9615A2678FB5D8ABC341503FF731871B9A127A5964CC7A1AA3956194"
REPOSITORY_ROOT = Path(__file__).parents[3]


def parse_crop(value: str) -> tuple[int, int, int, int]:
    coordinates = tuple(int(item) for item in value.split(","))
    if len(coordinates) != 4:
        raise argparse.ArgumentTypeError("crop must be x1,y1,x2,y2")
    return coordinates


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one PLAX-compatible full-cycle cine")
    parser.add_argument("input", type=Path)
    parser.add_argument("--model", type=Path, default=REPOSITORY_ROOT / "models/student_model/student_model_fp32.onnx")
    parser.add_argument("--head", type=Path, default=REPOSITORY_ROOT / "models/student_model/student_head.json")
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--crop", type=parse_crop, help="x1,y1,x2,y2 sector crop before resizing")
    args = parser.parse_args()
    model = OnnxWallModel(args.model, args.provider, MODEL_SHA256)
    frames = crop_frames(load_grayscale_cine(args.input), args.crop)
    result = analyze_cine(frames, model, load_frozen_head(args.head))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
