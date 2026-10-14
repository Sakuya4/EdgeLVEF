# PLAX Readiness Gate

The Readiness Gate summarizes PLAX view and image conditions from five-frame windows. It provides view, four-level readiness and five quality outputs as a separate system module.

## Architecture

MobileNetV3-Small extracts frame features, followed by global spatial pooling and mean pooling across five frames. A shared 256-channel MLP with Hardswish and dropout connects to three linear heads.

| Property | Specification |
|---|---|
| Parameters | 1,077,547 |
| Input | Five RGB frames; 224 × 224; ImageNet normalization |
| View output | Two logits |
| Readiness output | Four logits |
| Quality output | Five logits |
| Runtime artifact | FP32 ONNX; opset 17 |
| Artifact size | 4,323,007 bytes |

The five quality targets describe usable-image conditions, LV visibility, centering, completeness and PLAX proximity. View supervision uses EchoUNAL; readiness and quality targets are derived from EchoNet-LVH anatomy labels.

## Multi-task learning

```text
L = CE(view) + 0.7 CE(readiness) + 0.5 BCE(quality)
```

Quality loss uses an available-label mask. The Readiness Gate uses five-frame feature pooling. The LVEF Student uses its own temporal shift and temporal convolution pathway.

Across three training seeds, the proxy-label benchmark reports:

| Metric | Mean ± SD |
|---|---:|
| Readiness macro-F1 | 0.819 ± 0.019 |
| Standard-PLAX F1 | 0.875 ± 0.019 |
| Specificity | 0.680 ± 0.057 |
| False-ready rate | 0.320 ± 0.057 |

## Application interface

```bash
python -m pip install -e .
edgelvef-readiness path/to/plax_cine.mp4
```

The runtime samples up to 24 five-frame windows distributed across a cine and averages probabilities. The output JSON contains view, readiness, its probability, Standard-PLAX probability, five quality probabilities and the number of sampled windows.

The use case is `edgelvef.application.assess_readiness`, and the runtime adapter is `OnnxReadinessModel`. The source research repository is [PLAX-readiness-gate](https://github.com/Sakuya4/PLAX-readiness-gate).

The existing artifact and checksums are in [models/readiness_gate](../../models/readiness_gate/). Architecture publication does not modify that artifact or the application's output policy.
