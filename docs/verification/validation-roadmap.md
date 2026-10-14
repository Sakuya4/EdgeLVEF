# Evaluation design

EdgeLVEF evaluation connects study-level EF estimation with component and device measurements.

## EF estimation

Use patient-separated training, validation and evaluation partitions. Lock preprocessing, checkpoint and score threshold before inference. Aggregate eligible cines within each study and retain an accounting of all inputs.

Report MAE and RMSE in LVEF percentage points, bias, Pearson r, CCC, Bland–Altman limits and within-5/10-point rates. Report the screening head and numerical EF ≤ 40% rule separately. Paired model comparisons use aligned studies and an identified bootstrap resampling unit.

## Input and anatomical modules

Readiness Gate evaluation reports view and readiness classification alongside the source and definition of quality targets. Anatomical measurement adapters report localization, trajectory and measurement agreement. Their component metrics are recorded independently of the video Student's EF error.

## Runtime consistency

Maintain a fixed input set and artifact checksum. Compare workstation and device outputs through the complete preprocessing and temporal path. Record the selected execution provider and model version in each result.

Quantized and converted artifacts receive a new identity. Compare their outputs with the corresponding floating-point model using the same input set.

## Device measurements

Record end-to-end latency, per-model latency, memory, power and acquisition continuity on the physical board. The [embedded procedures](embedded-linux.md) define operator commands and environment fields. Existing measurement-adapter tests and selected video-Student measurements are identified by their model signatures.

## System operation

Evaluate acquisition, input review, inference, result display and reset as one device session. The local P42 adapter handles authorized SDK access and board-local transport; the Linux application handles display and result sessions. Record reconnection and service behavior alongside the model execution report.
