"""Minimal ultrasound DICOM cine decoding used by the training pipeline."""

from pathlib import Path

import cv2
import numpy as np
import pydicom


def decode_dicom(path: Path) -> tuple[np.ndarray, float]:
    dataset = pydicom.dcmread(path)
    pixels = np.asarray(dataset.pixel_array)
    if pixels.ndim == 2:
        pixels = pixels[None]
    elif pixels.ndim == 3 and pixels.shape[-1] in (3, 4):
        pixels = pixels[None]
    if pixels.ndim not in (3, 4):
        raise ValueError(f"Unsupported DICOM pixel shape: {pixels.shape}")
    if pixels.dtype != np.uint8:
        low, high = np.percentile(pixels, [1, 99])
        pixels = np.clip(
            (pixels.astype(np.float32) - low) * 255.0 / max(high - low, 1.0),
            0,
            255,
        ).astype(np.uint8)
    if getattr(dataset, "PhotometricInterpretation", "") == "MONOCHROME1":
        pixels = 255 - pixels
    if pixels.ndim == 4:
        pixels = np.stack(
            [cv2.cvtColor(frame[..., :3], cv2.COLOR_RGB2GRAY) for frame in pixels]
        )
    fps = float(
        getattr(dataset, "CineRate", 0)
        or getattr(dataset, "RecommendedDisplayFrameRate", 0)
        or 0
    )
    frame_time = float(getattr(dataset, "FrameTime", 0) or 0)
    if fps <= 0 and frame_time > 0:
        fps = 1000.0 / frame_time
    return pixels, fps if fps > 0 else 50.0
