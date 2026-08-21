import numpy as np

from edgelvef.domain.lvef import FrozenEdgeHead
from edgelvef.domain.wall_tracking import cycle_wall_features


def synthetic_probabilities() -> np.ndarray:
    probabilities = np.zeros((20, 2, 64, 64), dtype=np.float32)
    for frame in range(20):
        distance = 30 if frame < 4 else 20 if frame < 14 else 27
        for x in range(8, 56):
            probabilities[frame, 0, 15:18, x] = 0.95
            probabilities[frame, 1, 15 + distance:18 + distance, x] = 0.95
    return probabilities


def test_cycle_wall_features_detect_shortening():
    features = cycle_wall_features(synthetic_probabilities())
    assert features["valid_frame_fraction"] == 1.0
    assert 0.2 < features["global_fs"] < 0.5


def test_frozen_head_has_explicit_score_direction():
    head = FrozenEdgeHead(40.0, 40.0, -0.225)
    assert head.estimate_lvef(0.25) == 50.0
    assert head.predicts_low_ef(0.20)
    assert not head.predicts_low_ef(0.30)
