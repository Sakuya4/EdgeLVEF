from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


class OnnxReadinessModel:
    def __init__(
        self,
        model_path: Path,
        provider: str = "CPUExecutionProvider",
        expected_sha256: str | None = None,
        max_windows: int = 24,
        batch_size: int = 8,
    ) -> None:
        if expected_sha256 is not None:
            actual = hashlib.sha256(model_path.read_bytes()).hexdigest().upper()
            if actual != expected_sha256.upper():
                raise ValueError(f"Readiness model checksum mismatch: {actual}")
        if provider not in ort.get_available_providers():
            raise ValueError(f"Unavailable ONNX Runtime provider: {provider}")
        self.session = ort.InferenceSession(str(model_path), providers=[provider])
        self.input_name = self.session.get_inputs()[0].name
        self.max_windows = max_windows
        self.batch_size = batch_size

    @staticmethod
    def _preprocess(grayscale_frames: np.ndarray) -> np.ndarray:
        resized = np.stack([
            cv2.resize(frame, (224, 224), interpolation=cv2.INTER_AREA)
            for frame in grayscale_frames
        ])
        rgb = np.repeat(resized[:, None], 3, axis=1).astype(np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[None, :, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[None, :, None, None]
        return (rgb - mean) / std

    def predict_logits(
        self,
        grayscale_frames: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if grayscale_frames.ndim != 3 or len(grayscale_frames) < 5:
            raise ValueError("Expected at least 5 grayscale frames shaped [time, height, width]")
        possible_starts = np.arange(len(grayscale_frames) - 4)
        if len(possible_starts) > self.max_windows:
            indices = np.linspace(0, len(possible_starts) - 1, self.max_windows).round().astype(int)
            possible_starts = possible_starts[indices]
        normalized = self._preprocess(grayscale_frames)
        clips = np.stack([normalized[start : start + 5] for start in possible_starts])
        outputs = [[], [], []]
        for start in range(0, len(clips), self.batch_size):
            batch_outputs = self.session.run(None, {self.input_name: clips[start : start + self.batch_size]})
            for target, values in zip(outputs, batch_outputs):
                target.append(values)
        return tuple(np.concatenate(values) for values in outputs)  # type: ignore[return-value]
