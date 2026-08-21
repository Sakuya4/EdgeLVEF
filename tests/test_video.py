import numpy as np
import pytest

from edgelvef.infrastructure.video import crop_frames


def test_crop_frames_uses_xy_coordinates():
    frames = np.zeros((2, 10, 12), dtype=np.uint8)
    assert crop_frames(frames, (2, 3, 8, 9)).shape == (2, 6, 6)


def test_crop_frames_rejects_out_of_bounds_coordinates():
    with pytest.raises(ValueError, match="outside"):
        crop_frames(np.zeros((2, 10, 12), dtype=np.uint8), (0, 0, 13, 9))
