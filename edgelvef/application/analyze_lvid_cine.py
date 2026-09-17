from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..domain.interpretable_lvef import MonotonicLvefCalibration
from .ports import LvidTrajectoryModel


@dataclass(frozen=True)
class InterpretableLvefAnalysis:
    lvef_percent: float
    lvidd_px: float
    lvids_px: float
    lvid_ratio: float
    ed_frame: int
    es_frame: int
    median_endpoint_confidence: float
    predicts_lvef_at_or_below_40: bool
    inside_development_ratio_range: bool
    input_frames: int

    def to_dict(self) -> dict[str, float | bool | int | str]:
        return {
            **asdict(self),
            "method": "role-invariant LVID tracker plus monotonic three-parameter calibration",
            "warning": "Development-calibrated research output; not externally or clinically validated.",
        }


def analyze_lvid_cine(
    grayscale_frames: np.ndarray,
    fps: float,
    tracker: LvidTrajectoryModel,
    calibration: MonotonicLvefCalibration,
) -> InterpretableLvefAnalysis:
    trajectory = tracker.track(grayscale_frames, fps)
    curve = np.asarray(trajectory["smoothed_lvid_px"], dtype=np.float64)
    ed_frame = int(np.argmax(curve))
    es_frame = int(np.argmin(curve))
    estimate = calibration.estimate(float(curve[ed_frame]), float(curve[es_frame]))
    return InterpretableLvefAnalysis(
        lvef_percent=float(estimate["lvef_percent"]),
        lvidd_px=float(estimate["lvidd_px"]),
        lvids_px=float(estimate["lvids_px"]),
        lvid_ratio=float(estimate["lvid_ratio"]),
        ed_frame=ed_frame,
        es_frame=es_frame,
        median_endpoint_confidence=float(trajectory["median_confidence"]),
        predicts_lvef_at_or_below_40=bool(estimate["predicts_lvef_at_or_below_40"]),
        inside_development_ratio_range=bool(estimate["inside_development_ratio_range"]),
        input_frames=len(grayscale_frames),
    )
