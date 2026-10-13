from __future__ import annotations

import numpy as np

from ..domain.readiness import ReadinessAssessment, summarize_readiness
from .ports import ReadinessLogitModel


def assess_readiness(
    grayscale_frames: np.ndarray,
    model: ReadinessLogitModel,
) -> ReadinessAssessment:
    if grayscale_frames.ndim != 3 or len(grayscale_frames) < 5:
        raise ValueError("Expected at least 5 grayscale frames shaped [time, height, width]")
    return summarize_readiness(*model.predict_logits(grayscale_frames))
