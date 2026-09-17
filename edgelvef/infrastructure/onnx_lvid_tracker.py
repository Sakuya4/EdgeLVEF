from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


def _smooth_curve(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) < 5:
        return values.astype(np.float64)
    window = max(5, min(11, window))
    if window % 2 == 0:
        window += 1
    if window > len(values):
        window = len(values) if len(values) % 2 else len(values) - 1
    if window < 5:
        return values.astype(np.float64)
    half = window // 2
    output = np.empty(len(values), dtype=np.float64)
    for index in range(len(values)):
        start = min(max(index - half, 0), len(values) - window)
        positions = np.arange(start, start + window, dtype=np.float64) - index
        design = np.column_stack((np.ones(window), positions, positions**2))
        output[index] = np.linalg.lstsq(design, values[start : start + window], rcond=None)[0][0]
    return output


class OnnxLvidTracker:
    """ONNX adapter for the frozen role-invariant two-endpoint LVID tracker."""

    def __init__(
        self,
        model_path: Path,
        provider: str = "CPUExecutionProvider",
        expected_sha256: str | None = None,
        batch_size: int = 32,
    ):
        if expected_sha256 is not None:
            actual = hashlib.sha256(model_path.read_bytes()).hexdigest().upper()
            if actual != expected_sha256.upper():
                raise ValueError(f"Model checksum mismatch: {actual}")
        if provider not in ort.get_available_providers():
            raise ValueError(f"Unavailable ONNX Runtime provider: {provider}")
        self.session = ort.InferenceSession(str(model_path), providers=[provider])
        self.input_name = self.session.get_inputs()[0].name
        self.batch_size = batch_size

    @staticmethod
    def _windows(frames: np.ndarray) -> np.ndarray:
        resized = np.stack(
            [cv2.resize(frame, (256, 256), interpolation=cv2.INTER_AREA) for frame in frames]
        ).astype(np.float32) / 255.0
        indices = np.arange(len(resized))
        windows = np.stack(
            [resized[np.clip(indices + offset, 0, len(resized) - 1)] for offset in (-1, 0, 1)],
            axis=1,
        )
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[None, :, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[None, :, None, None]
        return (windows - mean) / std

    def track(self, grayscale_frames: np.ndarray, fps: float) -> dict[str, np.ndarray | float]:
        if grayscale_frames.ndim != 3 or len(grayscale_frames) < 5:
            raise ValueError("Expected at least five grayscale frames shaped [time, height, width]")
        if fps <= 0:
            raise ValueError("FPS must be greater than zero")
        windows = self._windows(grayscale_frames)
        points = []
        confidences = []
        for start in range(0, len(windows), self.batch_size):
            logits = self.session.run(
                None, {self.input_name: windows[start : start + self.batch_size]}
            )[0]
            flat = logits.reshape(len(logits), 2, -1)
            indices = flat.argmax(axis=-1)
            points.append(np.stack((indices % 256, indices // 256), axis=-1).astype(np.float32))
            peaks = flat.max(axis=-1)
            sigmoid = 1.0 / (1.0 + np.exp(-np.clip(peaks, -60.0, 60.0)))
            confidences.append(np.sqrt(sigmoid[:, 0] * sigmoid[:, 1]))
        endpoints = np.concatenate(points)
        confidence = np.concatenate(confidences)
        raw = np.linalg.norm(endpoints[:, 0] - endpoints[:, 1], axis=-1)
        window = int(round(0.12 * fps))
        smoothed = _smooth_curve(raw, window)
        return {
            "endpoints_xy_256": endpoints,
            "raw_lvid_px": raw,
            "smoothed_lvid_px": smoothed,
            "confidence": confidence,
            "median_confidence": float(np.median(confidence)),
        }
