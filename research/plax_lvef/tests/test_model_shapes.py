import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from plax_lvef.model import EdgeLvefModel  # noqa: E402


def test_selected_student_output_shapes():
    model = EdgeLvefModel(
        variant="mobilenet_v3_large",
        pretrained=False,
        temporal_model="tsm",
    ).eval()
    with torch.inference_mode():
        lvef, latent_trace, low_ef = model(torch.zeros(2, 4, 1, 112, 112))
    assert lvef.shape == (2,)
    assert latent_trace.shape == (2, 4)
    assert low_ef.shape == (2,)
    assert sum(parameter.numel() for parameter in model.parameters()) == 3_212_755
