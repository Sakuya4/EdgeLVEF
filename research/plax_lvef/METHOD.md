# Method

## 1. Task definition

The model estimates continuous LVEF from PLAX B-mode cine loops and provides a
secondary score for screening report-linked LVEF <= 40%. The evaluation unit is
the examination/study, never an individual frame. All data partitions are
patient-disjoint.

## 2. Offline Teacher

Each Teacher is an R(2+1)D-18 network initialized from Kinetics-400. A training
sample contains 64 RGB-repeated grayscale frames at 112 x 112, sampled with
stride 2. Global spatiotemporal average pooling feeds a linear LVEF regressor.
Two Teachers are trained with different random seeds and effective batch sizes;
their predictions and 512-dimensional encoder features are averaged.

Teacher optimization uses MSE to report-linked LVEF, RAdam with learning rate
`1e-3`, gradient accumulation, validation-MAE checkpoint selection and early
stopping. Low-EF-enriched training sampling is study-balanced; validation and
test prevalence are unchanged.

## 3. Edge Student

The selected Student receives 32 uniformly sampled grayscale frames at
112 x 112. Its components are:

1. MobileNetV3-Large 2-D frame encoder with a single-channel input stem;
2. temporal shift before the final four encoder blocks;
3. a 960-to-128 frame projection;
4. three residual depthwise-separable temporal convolution blocks with
   dilations 1, 2 and 4;
5. concatenated temporal mean and maximum pooling;
6. continuous LVEF and low-EF heads.

The deployable graph contains 3,212,755 parameters. A 256-to-512 projection is
used only during training to match the Teacher representation.

`model.py` also returns a framewise scalar named `volume_curve` for historical
interface compatibility. The locked M5-G training objective does not directly
supervise that output. It must therefore be treated as an unvalidated latent
trace, not as a ventricular volume measurement or clinical contraction curve.

## 4. Distillation objective

The locked Student loss is

```text
L = Huber(y_student, y_report)
  + 0.50 Huber(y_student, y_teacher)
  + 0.20 BCE(z_lowEF, p_teacher_lowEF)
  + 0.10 [1 - cosine(P(h_student), h_teacher)]
```

where `p_teacher_lowEF = sigmoid((40 - y_teacher) / 5)`. This is a heuristic
temperature-scaled soft target derived from the Teacher's continuous estimate,
not an independent Teacher classification head or empirically calibrated probability.

Student optimization uses AdamW (`3e-4`, weight decay `1e-4`), cosine learning
rate decay, gradient clipping at 1.0 and validation-MAE checkpoint selection.
Training samples from low-EF studies receive threefold weight after correcting
for the number of cines per study.

## 5. Evaluation protocol

- patient-disjoint train, validation and development-test partitions;
- threshold selection on validation only;
- study-level averaging across eligible cines;
- continuous metrics: MAE, RMSE, bias, Pearson correlation, CCC and
  within-5/10-percentage-point rates;
- screening metrics: AUROC, AUPRC, sensitivity, specificity and F1;
- literal numerical analysis based on predicted LVEF <= 40%;
- patient-level bootstrap intervals for selected comparisons.

The two-Teacher ensemble reached MAE 5.635 and normal-stress-analysis AUROC 0.992. The selected
MobileNetV3-Large Student reached MAE 5.471 and AUROC 0.964. The paired Student
minus Teacher MAE difference was -0.163 percentage points with 95% bootstrap
interval [-1.043, 0.710], which does not establish superiority of either model.

## 6. Claim boundary

The evidence supports a compact spatiotemporal Student on a fixed internal
development split. It does not establish cross-device robustness, external
generalization, clinical equivalence, diagnostic autonomy, INT8 fidelity or
physical i.MX93 latency. Teacher stress testing also found sensitivity to
peripheral masking, which is a shortcut/domain-shift warning.
