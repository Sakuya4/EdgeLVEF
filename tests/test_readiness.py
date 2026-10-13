import numpy as np

from edgelvef.domain.readiness import summarize_readiness
from edgelvef.application.assess_readiness import assess_readiness


def test_summarize_readiness_averages_windows():
    result = summarize_readiness(
        np.array([[0.0, 2.0], [0.0, 2.0]], dtype=np.float32),
        np.array([[0.0, 0.0, 0.0, 3.0], [0.0, 0.0, 0.0, 3.0]], dtype=np.float32),
        np.zeros((2, 5), dtype=np.float32),
    )
    assert result.view == "PLAX"
    assert result.readiness_level == "Standard PLAX"
    assert result.sampled_windows == 2
    assert result.standard_plax_probability > 0.8


def test_summarize_readiness_rejects_wrong_shapes():
    import pytest

    with pytest.raises(ValueError):
        summarize_readiness(np.zeros((1, 3)), np.zeros((1, 4)), np.zeros((1, 5)))


def test_application_rejects_short_cine_before_inference():
    import pytest

    class NeverCalled:
        def predict_logits(self, frames):
            raise AssertionError("Invalid input must not reach inference")

    with pytest.raises(ValueError):
        assess_readiness(np.zeros((4, 32, 32), dtype=np.uint8), NeverCalled())
