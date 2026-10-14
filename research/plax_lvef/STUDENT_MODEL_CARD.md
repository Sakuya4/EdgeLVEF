# Edge LVEF Student

The Student integrates frame appearance and cardiac motion in a compact PLAX video network.

| Stage | Design |
|---|---|
| Input | 32 uniformly sampled grayscale frames, 112 × 112 |
| Frame encoder | MobileNetV3-Large with single-channel stem |
| Temporal exchange | TSM before the final four encoder blocks |
| Projection | 960 → 128 channels per frame |
| Temporal integration | Three residual depthwise-separable blocks; dilations 1, 2, 4 |
| Pooling | Concatenated temporal mean and maximum |
| Video feature | 256 dimensions |
| Output heads | Continuous EF and low-EF logit |
| Parameter count | 3,212,755 |

The training-only 256 → 512 projector aligns Student features with the ensemble representation. The objective combines report EF, Teacher EF, Teacher-derived low-EF soft targets and cosine feature alignment. The selected network is trained with AdamW, 32-frame inputs and validation-MAE checkpoint selection.

On the 82-study development benchmark, the Student reaches MAE 5.471 pp, low-EF MAE 5.277 pp, RMSE 7.153 pp, AUROC 0.964 and screening F1 0.885. The [results page](RESULTS.md) reports the full comparison and the separate numerical EF ≤ 40% analysis.

`EdgeLvefModel(variant="mobilenet_v3_large", temporal_model="tsm")` is the training implementation. `EdgeLvefStudent(variant="mobilenet_v3_large")` is the importable architecture. Both retain checkpoint-compatible module names, including an auxiliary per-frame output. The application-facing outputs described here are EF and low-EF score.

Teacher models and the feature projector are excluded from Student inference. No trained LVEF weights are included in this method publication.
