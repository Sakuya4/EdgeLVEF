# PLAX video Teacher–Student learning

## Research objective

We estimate continuous LVEF from PLAX B-mode cines while reducing the network size required for local computation. Our design transfers high-capacity spatiotemporal supervision to a 2-D frame encoder with a compact temporal path. Evaluation and prediction aggregation operate at the study level.

## Teacher representation

Each Teacher is an R(2+1)D-18 network initialized from Kinetics-400. Spatial and temporal convolutions encode 64 grayscale frames repeated across three channels, sampled at stride 2 and resized to 112 × 112. Global spatiotemporal pooling produces a 512-dimensional feature, followed by a linear EF head.

Two independently trained Teachers provide an ensemble EF target and averaged feature representation. Report-linked EF supervises Teacher regression. Training samples are balanced by study, with additional weight for EF ≤ 40%.

## Student representation

The Student receives 32 uniformly sampled grayscale frames at 112 × 112. A single-channel MobileNetV3-Large encoder extracts spatial features. Temporal shift is applied before the last four encoder blocks: one eighth of the channels is exchanged in each temporal direction, while the remaining channels stay in their original frames.

Spatial pooling yields a 960-dimensional feature for each frame. A linear projection maps this to 128 channels. Three residual blocks use depthwise temporal convolution followed by pointwise mixing, with dilations 1, 2 and 4. Concatenated temporal mean and maximum pooling forms the 256-dimensional video feature used by the EF and low-EF heads.

The architecture contains 3,212,755 parameters. Teacher inference and the 256 → 512 feature projector are used during training only. The forward interface also retains an auxiliary per-frame scalar for software compatibility; the EF path uses the pooled temporal representation described above.

## Multi-signal distillation

Let \(y\) be report-linked EF, \(\hat y_S\) the Student estimate, and \(\hat y_T\) the ensemble estimate. The training loss is

```text
L = Huber(EF_student, EF_report; δ = 5)
  + 0.50 Huber(EF_student, EF_teacher; δ = 5)
  + 0.20 BCEWithLogits(low_EF_logit, sigmoid((40 − EF_teacher) / 5))
  + 0.10 [1 − cosine(project(Student_feature), Teacher_feature)]
```

The regression terms carry continuous EF information. The soft target places additional learning signal around the 40% boundary. Feature alignment transfers the ensemble's representation to the Student through the training-only projector.

## Training settings

| Setting | Teacher | Student |
|---|---|---|
| Input | 64 frames; temporal stride 2 | 32 uniformly sampled frames |
| Resolution | 112 × 112 | 112 × 112 |
| Initialization | Kinetics-400 R(2+1)D-18 | ImageNet frame encoder |
| Optimizer | RAdam | AdamW |
| Learning rate | 1 × 10⁻³ | 3 × 10⁻⁴ |
| Weight decay | 0 | 1 × 10⁻⁴ |
| Student batch size | — | 8 |
| Student epoch budget | — | 30 |
| Early-stopping patience | 7 epochs | 7 epochs |
| Checkpoint selection | Validation EF MAE | Validation EF MAE |
| Student learning-rate schedule | — | Cosine decay |
| Gradient clipping | — | 1.0 |

Study-normalized sampling gives low-EF training examples threefold weight. Validation and evaluation preserve their original distributions. The selected Student checkpoint is epoch 18; training stopped after 25 epochs.

## Study-level evaluation

The selected PLAX subset contains 379 training studies, 84 validation studies and 82 development-test studies, with 2,115, 442 and 487 cines respectively. Patients belong to a single partition. Predictions from eligible cines are averaged within each study.

Continuous evaluation reports MAE and RMSE in percentage points, bias, Pearson r, CCC, Bland–Altman limits and within-5/10-point rates. Low-EF analysis reports both the learned screening score and the numerical rule `estimated EF ≤ 40%`. Their thresholds and metrics are listed separately on the [results page](RESULTS.md).

## Research foundations

The design follows video-based cardiac-function analysis [1], PLAX EF learning [2], factorized spatiotemporal encoding [3], mobile spatial encoding [4] and temporal shift [5]. Our implementation brings these components into an edge-oriented Teacher–Student learning and system integration workflow. Full citations are in [References](REFERENCES.md).
