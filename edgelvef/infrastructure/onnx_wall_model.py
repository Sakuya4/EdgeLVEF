from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


class OnnxWallModel:
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

    def predict(self, grayscale_frames: np.ndarray) -> np.ndarray:
        if grayscale_frames.ndim != 3:
            raise ValueError("Expected grayscale frames shaped [time, height, width]")
        resized = np.stack([
            cv2.resize(frame, (320, 320), interpolation=cv2.INTER_AREA)
            for frame in grayscale_frames
        ])
        tensor = np.repeat(resized[:, None], 3, axis=1).astype(np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[None, :, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[None, :, None, None]
        logits = np.concatenate([
            self.session.run(None, {self.input_name: (tensor[start:start + self.batch_size] - mean) / std})[0]
            for start in range(0, len(tensor), self.batch_size)
        ])
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))
