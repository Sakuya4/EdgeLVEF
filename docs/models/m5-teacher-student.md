# M5 PLAX Video Teacher and Edge Student

## Intended use

M5 is a research-only PLAX cine framework for experimental continuous LVEF
estimation and low-EF screening. It is not a medical device and has no
prospective clinical validation.

## Architecture

The Teacher is a two-seed ensemble of R(2+1)D-18 cine regressors initialized
from Kinetics-400. Each model consumes 64 frames at 112 x 112 and emits a
512-dimensional spatiotemporal representation followed by scalar LVEF.
Predictions are averaged across eligible cines and the two seeds.

The M5-E Student consumes 32 grayscale frames at 112 x 112. A shared
MobileNetV3-Small frame encoder, one temporal-shift location, and three
depthwise temporal residual blocks produce a 256-dimensional cine
representation. Separate heads emit continuous LVEF and a low-EF score. The
training-only 256-to-512 projector aligns Student and Teacher representations.

The locked distillation objective was:

`report Huber + 0.50 teacher-EF Huber + 0.20 teacher-low-EF BCE + 0.10 feature cosine`

## Development evidence

The fixed patient-disjoint development test contained 82 studies, including 33
with report-linked LVEF at or below 40%.

| Metric | Teacher ensemble | M5-E Student |
|---|---:|---:|
| Parameters | 31.30M per seed | 1.118M |
| LVEF MAE | 5.635 percentage points | 6.645 percentage points |
| Low-EF MAE | 4.224 | 6.012 |
| Pearson r | 0.848 | 0.739 |
| CCC | 0.805 | 0.678 |
| AUROC | 0.992 | 0.938 |
| AUPRC | 0.988 | 0.927 |
| Screening F1 | 0.928 | 0.811 |
| Literal predicted-LVEF <=40 sensitivity | 0.758 | 0.606 |
| Literal predicted-LVEF <=40 specificity | 1.000 | 1.000 |

The Student reduces parameters by 96.43% relative to one Teacher seed. Its MAE
was 1.011 points worse; paired patient-level bootstrap 95% CI was 0.083 to
1.914 points.

## Mechanism checks

Repeating one frame across the Teacher input worsened MAE from 5.635 to 11.692,
supporting use of changing cine content. Deterministic frame shuffling produced
MAE 6.402, so the current evidence does not establish that strict temporal
order is essential. Peripheral masking produced MAE 7.574, indicating spatial
context/domain sensitivity.

## Evidence boundary

- Labels are study-level, report-linked weak references; they are not
  PLAX-frame-specific core-lab measurements.
- Results use one patient-disjoint MIMIC development split, not an independent
  external clinical cohort.
- The Student passed the locked MAE, screening-F1 and parameter gates but
  narrowly missed the AUROC gate and missed the literal low-EF sensitivity
  gate.
- The per-frame trajectory output was not independently supervised in M5-E and
  must not be presented as a validated LV volume curve.
- INT8 accuracy and physical i.MX93 latency remain to be measured.

## Weight access

Weights are excluded from public GitHub because they are models derived from
credentialed MIMIC-IV-ECHO data. Checkpoint hashes are recorded under
`models/m5_teacher_student/artifact_manifest.json` for authorized local use.
