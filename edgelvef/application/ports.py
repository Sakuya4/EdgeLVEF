from __future__ import annotations

from typing import Protocol

import numpy as np


class WallProbabilityModel(Protocol):
    def predict(self, grayscale_frames: np.ndarray) -> np.ndarray:
        """Return wall probabilities shaped [frames, 2, height, width]."""


class LvidTrajectoryModel(Protocol):
    def track(self, grayscale_frames: np.ndarray, fps: float) -> dict[str, np.ndarray | float]:
        """Return the full-cine LVID trajectory and endpoint coordinates."""
