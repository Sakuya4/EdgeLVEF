# Thesis PLAX Readiness Gate

Fixed R1 multi-task MobileNetV3-Small, seed 42. This is the existing thesis
candidate, not a new training run or a post-hoc best-seed selection.

| Artifact | Purpose |
|---|---|
| `readiness_gate_mobilenetv3_small.onnx` | FP32 ONNX Runtime inference, opset 17 |
| `readiness_gate_mobilenetv3_small.pt` | Tensor-only PyTorch state dictionary |
| `readiness_config.json` | Input/output contract and label order |
| `SHA256SUMS` | Exact published artifact checksums |

Architecture: `edgelvef/research/readiness_gate.py`; model card, method,
development results and usage: [readiness-gate.md](../../docs/models/readiness-gate.md).

Load locally without downloading ImageNet weights:

```python
import torch
from edgelvef.research.readiness_gate import ReadinessGateModel

model = ReadinessGateModel()
state = torch.load("models/readiness_gate/readiness_gate_mobilenetv3_small.pt",
                   map_location="cpu", weights_only=True)
model.load_state_dict(state, strict=True)
model.eval()
```

The artifact has 1,077,547 parameters. Neither MIMIC credentialed data nor
EchoJEPA/EchoFM Teacher weights are included. This R1 candidate uses supervised
quality heads, not foundation-model distillation. Research/evaluation only;
see [weight terms](../../WEIGHTS_LICENSE.md) and the model card for provenance.
