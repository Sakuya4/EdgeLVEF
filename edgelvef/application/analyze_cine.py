from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..domain.lvef import FrozenEdgeHead
from ..domain.wall_tracking import cycle_wall_features
from .ports import WallProbabilityModel


@dataclass(frozen=True)
class CineAnalysis:
    lvef_percent: float
    low_ef_score: float
    low_ef_definition_percent: float
    predicts_lvef_at_or_below_40: bool
    global_fractional_shortening: float
    valid_frame_fraction: float
    mean_wall_confidence: float
    ed_phase_fraction: float
    es_phase_fraction: float
    input_frames: int

    def to_dict(self) -> dict[str, float | bool | int | str]:
        return {
            **asdict(self),
            "warning": "Research use only; not externally or clinically validated.",
        }


def analyze_cine(
    grayscale_frames: np.ndarray,
    model: WallProbabilityModel,
    head: FrozenEdgeHead,
) -> CineAnalysis:
    if grayscale_frames.ndim != 3 or len(grayscale_frames) < 16:
        raise ValueError("Expected at least 16 grayscale frames shaped [time, height, width]")
    features = cycle_wall_features(model.predict(grayscale_frames))
    global_fs = features["global_fs"]
    return CineAnalysis(
        lvef_percent=head.estimate_lvef(global_fs),
        low_ef_score=head.low_ef_score(global_fs),
        low_ef_definition_percent=head.low_ef_definition,
        predicts_lvef_at_or_below_40=head.predicts_low_ef(global_fs),
        global_fractional_shortening=global_fs,
        valid_frame_fraction=features["valid_frame_fraction"],
        mean_wall_confidence=features["mean_wall_confidence"],
        ed_phase_fraction=features["ed_phase_fraction"],
        es_phase_fraction=features["es_phase_fraction"],
        input_frames=len(grayscale_frames),
    )
