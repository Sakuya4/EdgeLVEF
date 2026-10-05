# Student Model Card: M5-G MobileNetV3-Large TSM

## Role

M5-G is the selected compact LVEF deployment candidate. The Teacher ensemble,
feature projector and all distillation losses are absent at inference.

## Architecture

- Input: 32 uniformly sampled grayscale PLAX frames, 112 x 112.
- Frame encoder: MobileNetV3-Large with a single-channel stem.
- Temporal exchange: Temporal Shift Module before the final encoder stage.
- Temporal head: 960-to-128 projection followed by depthwise TCN residual
  blocks with dilations 1, 2 and 4.
- Pooling: concatenated temporal mean and maximum.
- Outputs: continuous LVEF and low-EF score.
- Parameters: 3,212,755 (approximately 19.5x fewer than the two-Teacher
  ensemble and 9.7x fewer than one Teacher).

## Training-only distillation

```text
L = Huber(student EF, report EF)
  + 0.50 Huber(student EF, ensemble EF)
  + 0.20 BCE(student low-EF logit, Teacher-derived soft probability)
  + 0.10 cosine distance(projected Student feature, Teacher feature)
```

The soft probability is `sigmoid((40 - teacher EF) / 5)`. The 256-to-512
Student feature projector is discarded at inference.

## Development results

On the same fixed 82-study development test:

| Metric | Result |
| --- | ---: |
| LVEF MAE | 5.471 pp |
| RMSE | 7.153 pp |
| Low-EF MAE | 5.277 pp |
| Bias | -0.890 pp |
| Pearson r | 0.835 |
| CCC | 0.818 |
| AUROC | 0.964 |
| AUPRC | 0.956 |
| Screening F1 | 0.885 |
| Literal LVEF <= 40% sensitivity | 0.727 |
| Literal LVEF <= 40% specificity | 1.000 |
| Within 5 pp | 0.634 |
| Within 10 pp | 0.780 |

Student minus Teacher paired MAE was -0.163 pp with 95% patient-bootstrap
interval [-1.043, 0.710]. This does not prove Student superiority or
equivalence; it shows no statistically established MAE difference on this
development cohort.

## Important implementation boundary

The historical interface returns a framewise `volume_curve`, but the locked
M5-G objective does not directly supervise it. Do not use or describe that
output as a validated ventricular volume or contraction curve.
