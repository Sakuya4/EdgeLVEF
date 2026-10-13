from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...application.assess_readiness import assess_readiness
from ...infrastructure.onnx_readiness_model import OnnxReadinessModel
from ...infrastructure.video import crop_frames, load_grayscale_cine


MODEL_SHA256 = "96A9E231A45EED2AB833ABD43ACD05C6E78E4F8FAC30A581808A408A1A12032E"
REPOSITORY_ROOT = Path(__file__).parents[3]


def parse_crop(value: str) -> tuple[int, int, int, int]:
    try:
        coordinates = tuple(int(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("crop must be x1,y1,x2,y2") from exc
    if len(coordinates) != 4:
        raise argparse.ArgumentTypeError("crop must be x1,y1,x2,y2")
    return coordinates


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess PLAX view/readiness/quality without changing LVEF output")
    parser.add_argument("input", type=Path)
    parser.add_argument("--model", type=Path, default=REPOSITORY_ROOT/"models/readiness_gate/readiness_gate_mobilenetv3_small.onnx")
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--crop", type=parse_crop, help="x1,y1,x2,y2 sector crop before resizing")
    args = parser.parse_args()
    frames = crop_frames(load_grayscale_cine(args.input), args.crop)
    model = OnnxReadinessModel(args.model, args.provider, MODEL_SHA256)
    print(json.dumps(assess_readiness(frames, model).to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
