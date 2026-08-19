from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from .model import EdgeLvefModel


VIDEO_SUFFIXES = {".avi", ".mov", ".mp4", ".mkv"}


def parse_crop(value: str) -> tuple[int, int, int, int]:
    coordinates = tuple(int(item) for item in value.split(","))
    if len(coordinates) != 4:
        raise argparse.ArgumentTypeError("crop must be x1,y1,x2,y2")
    return coordinates


def load_video(path: Path) -> np.ndarray:
    capture = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()
    if not frames:
        raise ValueError(f"No video frames could be read from {path}")
    return np.stack(frames)


def load_frames(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            if "frames" not in archive:
                raise ValueError("NPZ input must contain a 'frames' array")
            frames = np.asarray(archive["frames"])
    elif path.suffix.lower() in VIDEO_SUFFIXES:
        frames = load_video(path)
    else:
        raise ValueError(f"Unsupported input type: {path.suffix}")
    if frames.ndim == 4 and frames.shape[-1] in (3, 4):
        frames = np.stack([cv2.cvtColor(frame[..., :3], cv2.COLOR_RGB2GRAY) for frame in frames])
    if frames.ndim != 3 or len(frames) == 0:
        raise ValueError("Expected frames shaped [time, height, width]")
    return frames


def preprocess(
    frames: np.ndarray,
    frame_count: int,
    image_size: int,
    crop: tuple[int, int, int, int] | None,
) -> torch.Tensor:
    if crop is not None:
        x1, y1, x2, y2 = crop
        if not (0 <= x1 < x2 <= frames.shape[2] and 0 <= y1 < y2 <= frames.shape[1]):
            raise ValueError("Crop falls outside the video frame")
        frames = frames[:, y1:y2, x1:x2]
    indices = np.rint(np.linspace(0, len(frames) - 1, frame_count)).astype(np.int64)
    selected = [cv2.resize(frames[index], (image_size, image_size)) for index in indices]
    tensor = torch.from_numpy(np.stack(selected).copy()).float().div(255.0)
    return tensor.unsqueeze(0).unsqueeze(2)


def load_model(path: Path, device: torch.device) -> tuple[EdgeLvefModel, dict]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("model") != "mobilenet_v3_small" or checkpoint.get("temporal_model") != "tcn":
        raise ValueError(f"Unsupported checkpoint configuration: {path}")
    model = EdgeLvefModel(checkpoint["label_mean"], checkpoint["label_std"])
    model.load_state_dict(checkpoint["state_dict"])
    model.to(device).eval()
    return model, checkpoint


def run(args: argparse.Namespace) -> dict:
    checkpoint_paths = sorted(args.checkpoints.glob("fold*.pt"))
    if not checkpoint_paths:
        raise FileNotFoundError(f"No fold*.pt checkpoints found in {args.checkpoints}")
    device = torch.device(args.device)
    frames = load_frames(args.input)
    models = [load_model(path, device) for path in checkpoint_paths]
    frame_counts = {checkpoint["frames"] for _, checkpoint in models}
    image_sizes = {checkpoint["image_size"] for _, checkpoint in models}
    if len(frame_counts) != 1 or len(image_sizes) != 1:
        raise ValueError("Ensemble checkpoints use inconsistent preprocessing")
    tensor = preprocess(frames, frame_counts.pop(), image_sizes.pop(), args.crop).to(device)
    predictions = []
    probabilities = []
    with torch.inference_mode():
        for model, _ in models:
            lvef, probability = model(tensor)
            predictions.append(float(lvef.item()))
            probabilities.append(float(probability.item()))
    return {
        "input": str(args.input),
        "input_frames": int(len(frames)),
        "lvef_percent": round(float(np.mean(predictions)), 2),
        "model_std_percent": round(float(np.std(predictions)), 2),
        "fold_predictions_percent": [round(value, 2) for value in predictions],
        "low_ef_probability_research_only": round(float(np.mean(probabilities)), 4),
        "warning": "Research use only; not clinically validated.",
    }


def main() -> None:
    default_checkpoints = Path(__file__).parents[1] / "checkpoints" / "student_v4"
    parser = argparse.ArgumentParser(description="Run the EdgeLVEF Student v4 ensemble")
    parser.add_argument("input", type=Path)
    parser.add_argument("--checkpoints", type=Path, default=default_checkpoints)
    parser.add_argument("--crop", type=parse_crop)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
