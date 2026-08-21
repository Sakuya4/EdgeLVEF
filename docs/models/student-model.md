# Student Model card

## Intended use

Technical evaluation of two opposing endocardial wall trajectories in
PLAX-compatible echocardiography cines. The model supports research on
full-cycle fractional shortening and low-LVEF screening.

It is not approved for clinical diagnosis, triage, or treatment decisions.

## Artifact

| Property | Value |
|---|---|
| File | `models/student_model/student_model_fp32.onnx` |
| SHA-256 | `FE5FC82B9615A2678FB5D8ABC341503FF731871B9A127A5964CC7A1AA3956194` |
| Size | 3,955,338 bytes / 3.77 MiB |
| Parameters | 985,634 |
| Input | float32 RGB NCHW, ImageNet normalized, 320 x 320 |
| Output | two wall-logit maps, 320 x 320 |
| ONNX opset | 17 |

The preprocessing adapter accepts grayscale cine frames, resizes them to
320 x 320, repeats the channel to RGB, and applies ImageNet normalization.

## Frozen head

The development-only mapping uses 93 exams from EchoXFlow folds 0--2:

```text
LVEF = 40.8377138 + 40.0826932 * global_fractional_shortening
low_EF_score = -global_fractional_shortening
low_EF_threshold = -0.2254883
```

The mapping is a research approximation. It must not be recalibrated on board
validation cases.

## Existing evidence

- Target-domain validation Dice: 0.645.
- Anterior-septal Dice: 0.762.
- Posterior-wall Dice: 0.528; this is the main localization weakness.
- Confirmatory raw global-FS AUROC: 0.902 on 68 exams with only five low-EF
  cases.
- Confirmatory continuous LVEF MAE: 6.57 percentage points.
- Low-EF continuous predictions remain biased upward.

## Deployment status

FP32 ONNX passed PyTorch numerical equivalence with maximum absolute logit
error `7.01e-5`. The existing exploratory INT8 conversion is not distributed
because it produced unacceptable local probability drift. Physical-board
latency, memory, NPU delegation, thermals, and power remain to be measured.
