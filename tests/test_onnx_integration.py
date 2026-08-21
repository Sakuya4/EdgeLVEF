from pathlib import Path

import numpy as np

from edgelvef.infrastructure.onnx_wall_model import OnnxWallModel


MODEL_SHA256 = "FE5FC82B9615A2678FB5D8ABC341503FF731871B9A127A5964CC7A1AA3956194"


def test_frozen_onnx_loads_and_returns_two_wall_maps():
    root = Path(__file__).parents[1]
    model = OnnxWallModel(
        root / "models/wall_student_v12/wall_curve_student_fp32.onnx",
        expected_sha256=MODEL_SHA256,
        batch_size=2,
    )
    probabilities = model.predict(np.zeros((2, 64, 64), dtype=np.uint8))
    assert probabilities.shape == (2, 2, 320, 320)
    assert np.isfinite(probabilities).all()
