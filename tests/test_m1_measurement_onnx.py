from pathlib import Path

import numpy as np

from edgelvef.infrastructure.onnx_m1_measurement_model import OnnxM1MeasurementModel


MODEL_SHA256 = "B9CBB77DB1D9762802074D8750968D9CEC7C97C8472C046EEFE160F139695B50"


def test_frozen_m1_model_returns_four_finite_measurements():
    root = Path(__file__).parents[1]
    model = OnnxM1MeasurementModel(
        root / "models/m1_measurement_baseline/m1_measurement_fp32.onnx",
        expected_sha256=MODEL_SHA256,
    )
    result = model.predict(np.zeros((3, 64, 64), dtype=np.uint8), [1])[0]
    assert set(result["measurements"]) == {"IVSd", "LVIDd", "LVIDs", "LVPWd"}
    for measurement in result["measurements"].values():
        assert np.isfinite(measurement["normalized_length"])
        assert np.isfinite(measurement["confidence"])
