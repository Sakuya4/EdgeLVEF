from pathlib import Path

import numpy as np

from edgelvef.infrastructure.onnx_lvid_tracker import OnnxLvidTracker


MODEL_SHA256 = "CC95301A37A131F3926EA85A2FAB7A86DDED13C5DD2501F21FEEAB4D213C6B42"


def test_frozen_lvid_tracker_returns_finite_trajectory():
    root = Path(__file__).parents[1]
    model = OnnxLvidTracker(
        root / "models/m1_lvef3/m1_lvid_tracker_fp32.onnx",
        expected_sha256=MODEL_SHA256,
    )
    result = model.track(np.zeros((5, 64, 64), dtype=np.uint8), fps=50.0)
    assert result["endpoints_xy_256"].shape == (5, 2, 2)
    assert result["smoothed_lvid_px"].shape == (5,)
    assert np.isfinite(result["smoothed_lvid_px"]).all()
