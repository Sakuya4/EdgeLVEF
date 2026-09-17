# M1-LVEF3 artifacts

- `m1_lvid_tracker_fp32.onnx`: 978,214-parameter role-invariant ShuffleNetV2
  LVID endpoint tracker, input `[batch,3,256,256]`, output
  `[batch,2,256,256]`.
- `balanced_calibration.json`: three-parameter monotonic conversion from
  `LVIDs/LVIDd` to development-calibrated LVEF.
- `export_report.json`: PyTorch-to-ONNX numerical equivalence record.
- `SHA256SUMS`: immutable artifact checksums.

Research use only. The calibration was evaluated by five-fold exam-level nested
development validation on 164 EchoXFlow exams, not on an untouched external
clinical cohort.
