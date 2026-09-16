# M1 measurement baseline model card

## Intended use

M1-A is the first frozen measurement-native baseline for locating PLAX
measurement endpoints on annotated ED/ES frames. It predicts endpoints for
IVSd, LVIDd, LVIDs, and LVPWd from three adjacent grayscale frames.

It is provided so collaborators can reproduce inference and evaluate conversion
on embedded Linux. It is not approved for diagnosis, triage, or treatment.

## Artifact

| Property | Value |
|---|---|
| File | `models/m1_measurement_baseline/m1_measurement_fp32.onnx` |
| SHA-256 | `B9CBB77DB1D9762802074D8750968D9CEC7C97C8472C046EEFE160F139695B50` |
| Size | 45,549,332 bytes / 43.44 MiB |
| Parameters | 11,386,632 |
| Estimated computation | 2.766 GMAC at batch 1 |
| Input | float32 NCHW, 3 x 256 x 256 |
| Output | eight endpoint-logit maps, 256 x 256 |
| ONNX opset | 17 |

The three channels are grayscale frames at `t-1`, `t`, and `t+1`, resized to
256 x 256 and normalized with ImageNet channel statistics. Output pairs are:

```text
0,1 IVSd   2,3 LVIDd   4,5 LVIDs   6,7 LVPWd
```

## Locked development result

The checkpoint was selected at epoch 5 on the fixed 596-exam selection subset.
The 604-file calibration subset and official EchoNet-LVH test split were not
used.

| Endpoint | MAE |
|---|---:|
| IVSd | 1.306 mm |
| LVIDd | 2.246 mm |
| LVIDs | 2.785 mm |
| LVPWd | 1.407 mm |
| Macro | 1.936 mm |

Fractional-shortening MAE was 5.82 percentage points, with bias -1.53 points
and Pearson correlation 0.635 on 539 paired development exams.

The released 39.63M-parameter EchoNet-LVH model remains a stronger same-split
accuracy comparator (macro MAE 1.703 mm). M1-A is a smaller, interpretable
baseline, not an accuracy-superiority claim.

## Export verification

PyTorch-to-ONNX verification passed with maximum absolute logit difference
`1.43e-5` and mean absolute difference `2.27e-6`.

## Run

```bash
pip install -e .
python scripts/run_m1_measurement.py input.mp4 --frame 30 --overlay outputs/m1_frame30.png
pytest -q tests/test_m1_measurement_onnx.py
```

The script reports normalized image-space lengths. Conversion to millimetres
requires valid physical calibration. ED/ES phase selection is external to this
baseline and must not be inferred from arbitrary single-frame output.

## Embedded status

The distributed artifact is FP32 ONNX. Memory capacity is compatible with the
i.MX93 EVK, but Ethos-U65 execution has not yet been demonstrated. An i.MX93
deployment claim requires full-integer TFLite conversion, Vela operator-coverage
inspection, and measured board latency, memory, thermals, and power.

## Data and license note

Training used the EchoNet-LVH development data. No source cine, patient data,
or released Cedars-Sinai checkpoint is included. The weight is research-only;
users must review `WEIGHTS_LICENSE.md` and applicable upstream dataset terms
before redistribution or commercial use.
