# PLAX LVEF model specification

| Property | Value |
|---|---|
| Task | Continuous LVEF estimation from PLAX B-mode cine |
| Training reference | Report-linked study EF |
| Teacher | Two R(2+1)D-18 regressors |
| Student | MobileNetV3-Large, TSM and depthwise temporal CNN |
| Aggregation | Study-level mean over eligible cines |
| Student parameters | 3,212,755 |
| Input | 32 grayscale frames, 112 × 112 |
| Output | LVEF estimate and low-EF score |

See the [Teacher](TEACHER_MODEL_CARD.md) and [Student](STUDENT_MODEL_CARD.md) component specifications. [Results](RESULTS.md) provides the cohort definitions, model comparisons and numerical EF-error metrics.

The public package contains architecture code, training implementation and aggregate results. Credentialed records and trained LVEF weights remain in access-controlled storage.
