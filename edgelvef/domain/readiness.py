from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


VIEW_LABELS = ("non-PLAX", "PLAX")
READINESS_LABELS = ("No View", "LV Visible", "Near PLAX", "Standard PLAX")
QUALITY_LABELS = ("usable_image", "lv_visible", "lv_centered", "lv_complete", "plax_proximity")


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponential = np.exp(shifted)
    return exponential / exponential.sum(axis=1, keepdims=True)


@dataclass(frozen=True)
class ReadinessAssessment:
    view: str
    view_probability: float
    readiness_level: str
    readiness_probability: float
    standard_plax_probability: float
    quality_probabilities: dict[str, float]
    sampled_windows: int

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "evidence_scope": "Pseudo-label development model; not clinician-rated readiness validation.",
        }


def summarize_readiness(
    view_logits: np.ndarray,
    readiness_logits: np.ndarray,
    quality_logits: np.ndarray,
) -> ReadinessAssessment:
    if view_logits.ndim != 2 or view_logits.shape[1] != len(VIEW_LABELS):
        raise ValueError("Expected view logits shaped [windows, 2]")
    if readiness_logits.shape != (len(view_logits), len(READINESS_LABELS)):
        raise ValueError("Expected readiness logits shaped [windows, 4]")
    if quality_logits.shape != (len(view_logits), len(QUALITY_LABELS)):
        raise ValueError("Expected quality logits shaped [windows, 5]")
    if not len(view_logits):
        raise ValueError("At least one readiness window is required")

    view_probabilities = _softmax(view_logits).mean(axis=0)
    readiness_probabilities = _softmax(readiness_logits).mean(axis=0)
    quality_probabilities = (1.0 / (1.0 + np.exp(-np.clip(quality_logits, -60.0, 60.0)))).mean(axis=0)
    view_index = int(view_probabilities.argmax())
    readiness_index = int(readiness_probabilities.argmax())
    return ReadinessAssessment(
        view=VIEW_LABELS[view_index],
        view_probability=float(view_probabilities[view_index]),
        readiness_level=READINESS_LABELS[readiness_index],
        readiness_probability=float(readiness_probabilities[readiness_index]),
        standard_plax_probability=float(readiness_probabilities[-1]),
        quality_probabilities={
            label: float(value) for label, value in zip(QUALITY_LABELS, quality_probabilities)
        },
        sampled_windows=len(view_logits),
    )
