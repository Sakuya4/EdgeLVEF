from pathlib import Path

import numpy as np

from edgelvef.infrastructure.overlay import render_wall_overlay
from test_domain import synthetic_probabilities


def test_overlay_writes_one_video(tmp_path: Path):
    output = tmp_path / "overlay.mp4"
    result = render_wall_overlay(
        np.zeros((20, 64, 64), dtype=np.uint8),
        synthetic_probabilities(),
        output,
    )
    assert output.is_file()
    assert output.stat().st_size > 0
    assert result["frames"] == 20
