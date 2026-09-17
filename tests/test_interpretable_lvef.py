import numpy as np

from edgelvef.application.analyze_lvid_cine import analyze_lvid_cine
from edgelvef.domain.interpretable_lvef import MonotonicLvefCalibration


class FakeTracker:
    def track(self, grayscale_frames: np.ndarray, fps: float) -> dict:
        curve = np.asarray([40.0, 45.0, 50.0, 42.0, 35.0, 38.0])
        return {
            "smoothed_lvid_px": curve,
            "median_confidence": 0.9,
        }


def test_analysis_exposes_measurements_and_calibrated_lvef():
    calibration = MonotonicLvefCalibration(-0.4811718, 0.6019632, 3.7896288)
    result = analyze_lvid_cine(np.zeros((6, 32, 32), dtype=np.uint8), 50.0, FakeTracker(), calibration)
    assert result.ed_frame == 2
    assert result.es_frame == 4
    assert result.lvidd_px == 50.0
    assert result.lvids_px == 35.0
    assert 0.0 <= result.lvef_percent <= 100.0
    assert "not externally" in result.to_dict()["warning"]


def test_calibration_decreases_as_residual_ratio_increases():
    calibration = MonotonicLvefCalibration(-0.4811718, 0.6019632, 3.7896288)
    stronger = calibration.estimate(50.0, 25.0)["lvef_percent"]
    weaker = calibration.estimate(50.0, 40.0)["lvef_percent"]
    assert stronger > weaker
