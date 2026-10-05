# Model Family Card: M5 Teacher–Student PLAX LVEF

## Components

- Offline Teacher: two R(2+1)D-18 cine regressors, 31,300,638 parameters each.
- Edge Student: MobileNetV3-Large + temporal shift + depthwise TCN,
  3,212,755 parameters.
- Task: PLAX cine to continuous LVEF and low-EF screening score.
- Supervision: report-linked weak LVEF plus Teacher output/feature distillation.

Detailed component cards are in `TEACHER_MODEL_CARD.md` and
`STUDENT_MODEL_CARD.md`.

## Intended use

Research and engineering evaluation of low-compute PLAX LVEF estimation. The
model may support a prototype edge pipeline after independent validation and
hardware profiling. It is not a medical device and must not independently
diagnose, triage or determine treatment.

## Development evidence

The fixed patient-disjoint development test contained 82 studies, including 33
with report-linked LVEF <= 40%. MAE was 5.471 percentage points, low-EF MAE
5.277, AUROC 0.964 and AUPRC 0.956. The validation-selected screening F1 was
0.885. Literal numerical sensitivity/specificity for predicted LVEF <= 40%
were 0.727/1.000.

## Limitations

1. Labels are report-linked and may not correspond exactly to the selected cine.
2. Results come from one inspected development split, not an external cohort.
3. No prospective clinician study or cross-device validation has been completed.
4. Peripheral masking degraded the Teacher, indicating shortcut/domain risk.
5. The returned `volume_curve` has no direct locked supervision and is not a
   validated volume or phase estimate.
6. INT8 accuracy and physical i.MX93 latency remain unverified.
7. The model can fail on non-PLAX, poor-quality or out-of-distribution inputs;
   a separately validated readiness/view gate is required at system level.

## Data and artifact governance

Raw data, identifiers, per-study predictions and trained restricted weights are
not included. The local checkpoint checksum is documented solely for internal
reproducibility. Access to credentialed data and restricted derivatives remains
subject to the applicable PhysioNet agreement.
