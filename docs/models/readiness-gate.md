# PLAX Readiness Gate model card

## Intended use

The Readiness Gate summarizes whether sampled five-frame windows resemble PLAX
and contain visible, centered, complete LV anatomy. It can provide input
condition evidence before the wall-motion result. It does not guide probe
motion and does not suppress the LVEF output in the competition prototype.

## Artifact

| Property | Value |
|---|---|
| File | `models/readiness_gate/readiness_gate_mobilenetv3_small.onnx` |
| SHA-256 | `96A9E231A45EED2AB833ABD43ACD05C6E78E4F8FAC30A581808A408A1A12032E` |
| Size | 4,323,007 bytes |
| Parameters | 1,077,547 |
| Input | five RGB frames, ImageNet normalized, 224 x 224 |
| Outputs | 2 view logits, 4 readiness logits, 5 quality logits |
| ONNX opset | 17 |

The runtime samples at most 24 five-frame windows distributed across a cine and
averages their probabilities. This cine aggregation is a competition-interface
choice and has not been independently validated.

## Development evidence

The fixed R1 MobileNetV3-Small multi-task experiment used public-data proxy
labels. Across three repeated seeds it reported readiness macro-F1
`0.819 +/- 0.019`, Standard-PLAX F1 `0.875 +/- 0.019`, specificity
`0.680 +/- 0.057`, and false-ready rate `0.320 +/- 0.057`.

These are pseudo-label benchmark results, not clinician-rated readiness
performance. EchoUNAL provides view supervision; EchoNet-LVH and landmark rules
provide anatomy proxies. The model must not be described as clinically proving
that a cine is suitable for LVEF measurement.

## Method and provenance

The shipped artifact is the thesis R1 `quality_multitask` candidate, fixed seed
42. MobileNetV3-Small extracts each frame's features; global spatial pooling
and mean pooling across five frames produce a cine-window embedding. A shared
256-channel MLP with Hardswish/dropout supplies three linear heads. This is
five-frame feature pooling, not TSM or an LVEF regressor.

The R1 task objective is `CE(view) + 0.7*CE(readiness) + 0.5*BCE(quality)`;
quality supervision uses the training protocol's available-label mask.
Q/V/C/K/P denote usable-image, LV-visible, LV-centered, LV-complete and
PLAX-proximity proxies. There is no foundation distillation term in R1;
EchoJEPA/EchoFM Teachers must not be presented as part of its inference path.

Source research repository: https://github.com/Sakuya4/PLAX-readiness-gate
Local source run identity: `runs/foundation_readiness/R1_quality_multitask/seed_42/best.pt`.
The tensor-only state dictionary is published as
`models/readiness_gate/readiness_gate_mobilenetv3_small.pt`; see `SHA256SUMS`.
The three-seed statistics above summarize seeds42/43/44, not the individual
published seed42 or this application's full-cine aggregation.

## Run from the repository checkout

```bash
python -m pip install -e .
python -m edgelvef.interfaces.cli.readiness path/to/plax_cine.mp4
python -m edgelvef.interfaces.cli.readiness path/to/plax_cine.mp4 --crop 20,30,300,280
# Installed entry point after editable install:
edgelvef-readiness path/to/plax_cine.mp4
```

The loader accepts MP4/AVI/MOV/MKV and NPZ with a `frames` array. Frames are
decoded as grayscale uint8. At least five frames are required. DICOM and live
SDK integration belong to acquisition adapters and are not added by this CLI.
The output JSON reports the view, selected readiness level, its probability,
Standard-PLAX probability, five quality probabilities and sampled-window count.

The application layer is `edgelvef.application.assess_readiness`; the runtime
adapter is `edgelvef.infrastructure.onnx_readiness_model.OnnxReadinessModel`.
Linux UI/acquisition code can call these independently of the LVEF models.
Existing LVEF commands and board UI behavior are unchanged by this publication.

## Verification and deployment scope

```bash
python -m pytest tests/test_readiness.py tests/test_readiness_onnx.py -q
```

Tests check shape/probability aggregation, checkpoint hash, all three heads,
matching PyTorch/ONNX logits on deterministic synthetic frames, variable batch
sizes and the independent CLI. Synthetic inputs verify implementation only;
they are not clinical validation or new accuracy measurements. This release
ships FP32 ONNX; no INT8 equivalence or physical i.MX93 NPU latency is asserted.
