# EdgeLVEF

PLAX-only research prototype for estimating LVEF from an echocardiography cine.
The current public checkpoint bundle is the **Student v4 five-fold ensemble**:
MobileNetV3-Small frame encoder with a lightweight temporal convolutional head.

> Research use only. This model is not a medical device and must not be used to
> diagnose or treat patients.

## Quick start

Python 3.11 is recommended.

```bash
git clone https://github.com/Sakuya4/EdgeLVEF.git
cd EdgeLVEF
python -m pip install -e .
python -m edgelvef.infer path/to/plax_cine.mp4
```

The input may be an `.mp4`, `.avi`, `.mov`, or an `.npz` containing a `frames`
array shaped `[time, height, width]`. Exactly 32 uniformly spaced frames are
resized to 112 x 112 grayscale images, matching training preprocessing.

If a video includes the full ultrasound-machine interface, crop it to the
sector before inference:

```bash
python -m edgelvef.infer cine.mp4 --crop 120,40,920,840
```

Example output:

```json
{
  "lvef_percent": 51.2,
  "model_std_percent": 2.1,
  "fold_predictions_percent": [49.8, 52.0, 50.7, 54.1, 49.4],
  "low_ef_probability_research_only": 0.31
}
```

`model_std_percent` measures disagreement among the five checkpoints. It is
not a validated clinical uncertainty interval. The low-EF probability is not
calibrated for external clinical use and no decision threshold is provided.

## Current evidence

Student v4 was evaluated by exam-level five-fold out-of-fold testing on 164
real reference exams, including 18 exams with LVEF <= 40%:

| Metric | Result |
|---|---:|
| LVEF MAE | 6.00 percentage points |
| LVEF RMSE | 7.76 percentage points |
| Pearson r | 0.298 |
| Low-EF AUROC | 0.694 |

These are out-of-fold results from the corresponding fold checkpoints, not a
prospective external validation of the five-model ensemble. The continuous
output regresses toward the population mean and missed the low-EF tail at the
literal 40% cutoff. Do not describe this release as clinically validated.

The strongest experimental low-EF result in the project is a structured
wall-motion probe (AUROC 0.892, AUPRC 0.582), but it is not included as a
deployable model because it still depends on a separate landmark Teacher. The
next research version will replace the single measurement line with opposing
PLAX wall tracking and regional fractional-shortening features.

## Files

- `edgelvef/model.py`: MobileNetV3-Small + temporal head definition.
- `edgelvef/infer.py`: video/NPZ preprocessing and ensemble inference.
- `checkpoints/student_v4/`: five fold-specific checkpoints.
- `MODEL_CARD.md`: scope, data provenance, metrics, and limitations.

## Data and weight terms

The checkpoints were trained using EchoXFlow-derived research data. EchoXFlow
is distributed under CC BY-NC-SA 4.0. This repository therefore limits the
released checkpoints to non-commercial research and evaluation; see
`WEIGHTS_LICENSE.md`. No source echocardiograms or patient-level data are
included.
