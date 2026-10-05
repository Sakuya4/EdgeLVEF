# EdgeLVEF paper evidence and reproducible research

Updated2026-10-05. This standalone research package does NOT change the Linux
App, probe connection, runtime model selection, or old measurement baselines.

## Start here

- [Writing Prompt](PAPER_WRITING_PROMPT.md): paste into another AI to request
  an English IEEE-style LaTeX manuscript and evidence audit.
- [Evidence ledger](EVIDENCE_LEDGER.md): numerical source-of-truth and claim boundaries.
- [Method](METHOD.md): successful M5 Teacher/Student architecture and objectives.
- [Results](RESULTS.md): Teacher comparison and six Student backbones.
- [Latest experiments](LATEST_EXPERIMENTS.md): M9/M10/M11 negative controls.
- [Reproduction](REPRODUCIBILITY.md): tests, data requirements and script entry points.

## Current selected candidate

M5-G MobileNetV3-Large + temporal shift + depthwise TCN,3,212,755 parameters.
On82 inspected development studies (33 report-linked low EF),MAE5.471pp,
low-EF MAE5.277pp,AUROC0.964,screeningF1 0.885. The two-model R(2+1)D
Teacher ensemble has62.60M parameters,MAE5.635pp. Lower Student MAE is a
point estimate; pairedCI crosses zero and does not establish superiority.

Older `docs/models/m5-teacher-student.md` describes the earlier M5-E
MobileNetV3-Small (1.118M,MAE6.645pp). It is not the selected M5-G model.
Do not mix the Small architecture/parameter count with Large results. This
package publishes the exact experimental Student architecture and training code;
it does not claim the application already uses this checkpoint.

## Strongest supported paper angle

An empirically evaluated PLAX-only accuracy/parameter trade-off: ensemble
spatiotemporal supervision transferred to a compact2-D+temporal Student, with
six-backbone comparisons and unsuccessful anatomy/motion extensions retained.
R(2+1)D,MobileNetV3,TSM and distillation are prior methods; composition is not
automatically a new algorithm. Clinical utility, first-in-field novelty, external
generalization and i.MX93 speed/INT8 fidelity are not established here.

## Privacy and artifact policy

Only source, aggregate results and research descriptions are included. No
MIMIC records,individual predictions,raw images,local caches,patient identifiers,
credentials,probe licenses or MIMIC-derived checkpoints are published. Authorized
users must obtain their own dataset access and comply with the applicable DUA.
Weight redistribution remains excluded pending a documented policy determination.

Smoke data are synthetic or tiny technical checks, never scientific evidence.
Do not infer clinical approval from a passing software test or journal-style PDF.
