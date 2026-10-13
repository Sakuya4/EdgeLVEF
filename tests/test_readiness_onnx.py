from pathlib import Path

import json
import subprocess
import sys

import numpy as np
import torch

from edgelvef.infrastructure.onnx_readiness_model import OnnxReadinessModel
from edgelvef.research.readiness_gate import ReadinessGateModel


MODEL_SHA256 = "96A9E231A45EED2AB833ABD43ACD05C6E78E4F8FAC30A581808A408A1A12032E"


def test_readiness_onnx_returns_all_three_heads():
    root = Path(__file__).parents[1]
    model = OnnxReadinessModel(
        root / "models/readiness_gate/readiness_gate_mobilenetv3_small.onnx",
        expected_sha256=MODEL_SHA256,
        max_windows=2,
    )
    view, readiness, quality = model.predict_logits(np.zeros((8, 32, 32), dtype=np.uint8))
    assert view.shape == (2, 2)
    assert readiness.shape == (2, 4)
    assert quality.shape == (2, 5)
    assert np.isfinite(view).all()


def test_pytorch_state_matches_published_onnx():
    root = Path(__file__).parents[1]
    model = ReadinessGateModel().eval()
    state = torch.load(root/"models/readiness_gate/readiness_gate_mobilenetv3_small.pt",
                       map_location="cpu", weights_only=True)
    assert all(isinstance(v, torch.Tensor) for v in state.values())
    model.load_state_dict(state, strict=True)
    assert sum(p.numel() for p in model.parameters()) == 1_077_547
    runtime = OnnxReadinessModel(root/"models/readiness_gate/readiness_gate_mobilenetv3_small.onnx",
                                 expected_sha256=MODEL_SHA256)
    rng = np.random.default_rng(42)
    for batch in (1, 2):
        clips = rng.normal(size=(batch, 5, 3, 224, 224)).astype(np.float32)
        with torch.inference_mode():
            expected = [x.numpy() for x in model(torch.from_numpy(clips))]
        actual = runtime.session.run(None, {runtime.input_name: clips})
        for lhs, rhs in zip(actual, expected):
            np.testing.assert_allclose(lhs, rhs, atol=1e-4, rtol=1e-4)


def test_readiness_cli_runs_without_lvef_models(tmp_path):
    root = Path(__file__).parents[1]
    fixture = tmp_path/"synthetic_cine.npz"
    np.savez(fixture, frames=np.zeros((5, 32, 32), dtype=np.uint8))
    result = subprocess.run([sys.executable, "-m", "edgelvef.interfaces.cli.readiness", str(fixture)],
                            cwd=root, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert payload["sampled_windows"] == 1
    assert set(payload["quality_probabilities"]) == {"usable_image", "lv_visible", "lv_centered", "lv_complete", "plax_proximity"}
    assert "lvef" not in payload
