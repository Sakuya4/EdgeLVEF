from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


MEASUREMENT_CHANNELS = {
    "IVSd": (0, 1),
    "LVIDd": (2, 3),
    "LVIDs": (4, 5),
    "LVPWd": (6, 7),
}


class OnnxM1MeasurementModel:
    """ONNX adapter for the frozen M1-A endpoint-heatmap baseline."""

    def __init__(
        self,
        model_path: Path,
        provider: str = "CPUExecutionProvider",
        expected_sha256: str | None = None,
    ):
        if expected_sha256 is not None:
            actual = hashlib.sha256(model_path.read_bytes()).hexdigest().upper()
            if actual != expected_sha256.upper():
                raise ValueError(f"Model checksum mismatch: {actual}")
        if provider not in ort.get_available_providers():
            raise ValueError(f"Unavailable ONNX Runtime provider: {provider}")
        self.session = ort.InferenceSession(str(model_path), providers=[provider])
        self.input_name = self.session.get_inputs()[0].name

    @staticmethod
    def _window(frames: np.ndarray, center: int) -> np.ndarray:
        indices = np.clip(np.asarray([center - 1, center, center + 1]), 0, len(frames) - 1)
        resized = np.stack(
            [cv2.resize(frames[index], (256, 256), interpolation=cv2.INTER_AREA) for index in indices]
        ).astype(np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
        return (resized - mean) / std

    def predict(self, grayscale_frames: np.ndarray, centers: list[int]) -> list[dict]:
        if grayscale_frames.ndim != 3 or len(grayscale_frames) == 0:
            raise ValueError("Expected non-empty grayscale frames shaped [time, height, width]")
        if not centers:
            raise ValueError("At least one center frame is required")
        if any(center < 0 or center >= len(grayscale_frames) for center in centers):
            raise ValueError("Center frame is outside the cine")
        batch = np.stack([self._window(grayscale_frames, center) for center in centers])
        logits = self.session.run(None, {self.input_name: batch})[0]
        flat = logits.reshape(len(centers), 8, -1)
        indices = flat.argmax(axis=-1)
        points = np.stack((indices % 256, indices // 256), axis=-1).astype(np.float32)
        confidence = 1.0 / (1.0 + np.exp(-np.clip(flat.max(axis=-1), -60.0, 60.0)))
        results = []
        for sample, center in enumerate(centers):
            measurements = {}
            for name, (first, second) in MEASUREMENT_CHANNELS.items():
                endpoints = points[sample, [first, second]]
                measurements[name] = {
                    "endpoints_xy_256": endpoints.tolist(),
                    "normalized_length": float(np.linalg.norm(endpoints[0] - endpoints[1]) / 256.0),
                    "confidence": float(min(confidence[sample, first], confidence[sample, second])),
                }
            results.append({"frame": center, "measurements": measurements})
        return results
