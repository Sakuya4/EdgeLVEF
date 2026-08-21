from edgelvef.application.analyze_cine import analyze_cine
from edgelvef.domain.lvef import FrozenEdgeHead
from test_domain import synthetic_probabilities


class FakeWallModel:
    def predict(self, grayscale_frames):
        return synthetic_probabilities()


def test_analyze_cine_uses_domain_features():
    import numpy as np

    result = analyze_cine(
        np.zeros((20, 64, 64), dtype=np.uint8),
        FakeWallModel(),
        FrozenEdgeHead(40.0, 40.0, -0.225),
    )
    assert result.input_frames == 20
    assert result.lvef_percent > 40
