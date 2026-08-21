from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


VIDEO_SUFFIXES = {".avi", ".mov", ".mp4", ".mkv"}


def load_grayscale_cine(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            if "frames" not in archive:
                raise ValueError("NPZ input must contain a 'frames' array")
            frames = np.asarray(archive["frames"])
    elif path.suffix.lower() in VIDEO_SUFFIXES:
        capture = cv2.VideoCapture(str(path))
        decoded = []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            decoded.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        capture.release()
        if not decoded:
            raise ValueError(f"No video frames could be read from {path}")
        frames = np.stack(decoded)
    else:
        raise ValueError(f"Unsupported input type: {path.suffix}")
    if frames.ndim == 4 and frames.shape[-1] in (3, 4):
        frames = np.stack([cv2.cvtColor(frame[..., :3], cv2.COLOR_RGB2GRAY) for frame in frames])
    if frames.ndim != 3 or not len(frames):
        raise ValueError("Expected frames shaped [time, height, width]")
    if frames.dtype != np.uint8:
        low, high = np.percentile(frames, [1, 99])
        frames = np.clip((frames.astype(np.float32) - low) * 255.0 / max(high - low, 1.0), 0, 255).astype(np.uint8)
    return frames


def crop_frames(frames: np.ndarray, crop: tuple[int, int, int, int] | None) -> np.ndarray:
    if crop is None:
        return frames
    x1, y1, x2, y2 = crop
    if not (0 <= x1 < x2 <= frames.shape[2] and 0 <= y1 < y2 <= frames.shape[1]):
        raise ValueError("Crop falls outside the video frame")
    return frames[:, y1:y2, x1:x2]
