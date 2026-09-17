# Low-LVEF competition improvement plan

Date: 2026-09-17
Scope: EdgeLVEF AI/LVEF modules only
Status: experiment plan; no training was started

## 1. Current evidence and the actual failure

M1-LVEF3 has nested five-fold development results on 164 EchoXFlow exams. Only
18 exams have reference LVEF <=40%.

| Item | Current result |
|---|---:|
| TP / FN / TN / FP | 9 / 9 / 145 / 1 |
| Sensitivity | 50.0% |
| Specificity | 99.3% |
| Accuracy | 93.9% |
| Balanced accuracy | 74.7% |
| Low-EF prevalence | 11.0% |
| Always-negative accuracy | 89.0% |
| Continuous-EF MAE | 5.236 percentage points |

Accuracy is not a useful primary metric here. The model misses half of the
true low-EF exams while making almost no false-positive calls. This is an
overly conservative operating point and may also reflect missing motion or
phase information.

The current released mapping classifies low EF when its estimated EF is <=40%.
For the released calibration, this corresponds to `LVIDs/LVIDd >= 0.744869`.
Changing the alert cutoff may recover some false negatives, but it cannot
improve ranking and must be selected inside training/validation folds. The
repository does not currently contain the per-exam OOF predictions needed to
test this safely.

The overall bias is -1.294 points, so a simple global downward correction is
unlikely to explain or fix all nine false negatives. A dedicated low-EF head
and ordered cardiac-motion features are needed.

## 2. Proposed model

Keep continuous LVEF and low-EF detection as related but separate outputs:

```text
PLAX cine
  |-- M1 endpoint/measurement sequence [T, 32]
  |-- frozen EchoJEPA foundation sequence [T, D]
  v
small ordered temporal adapter (TCN first; GRU as ablation)
  |-- EFRegressionHead -> continuous LVEF
  |-- LowEFHead       -> P(reference LVEF <= 40%)
  `-- quality/confidence output

Gao prediction -> optional auxiliary teacher signal for training only
```

Why this addresses the failure:

- M1 preserves interpretable LV diameter information.
- EchoJEPA can represent regional wall motion and image evidence that an LVID
  ratio alone misses.
- TCN preserves ED -> ES -> ED order; mean/std/min/max pooling does not.
- A separate classification head can learn the <=40% endpoint without forcing
  every decision through one three-parameter EF equation.
- Continuous EF remains available and is not replaced by the classifier.

EchoJEPA remains frozen for the first experiment. Full ViT-L fine-tuning is not
justified with 164 exams and 18 positive cases.

## 3. Data and split requirements

Training must wait until the authentic strong-label manifest and OOF records
are restored. Required fields are:

```text
patient_id, exam_id, recording_id, video_path, edv, esv, lvef, fold, label_source
```

Rules:

1. Group by patient, because EchoXFlow contains more exams than patients.
2. Put every recording from one exam in one fold.
3. Stratify folds by the <=40% endpoint as far as group constraints allow.
4. Fit calibration, loss weights and decision thresholds only on train/inner
   validation data.
5. Never oversample validation or test data.
6. Gao predictions and unlabeled PLAX may support representation learning or
   knowledge distillation, but are not ground truth.
7. Do not derive ground-truth EF from M1, Teichholz, or another teacher.

With only 18 positives, a single five-fold result is unstable. Report pooled
OOF predictions and patient-grouped bootstrap confidence intervals. Preserve
an untouched external or final holdout set before making competition accuracy
claims.

## 4. Training objective

For strong-label examples:

```text
L = L_huber(EF_pred, EF_true)
  + lambda_cls * BCEWithLogits(low_ef_logit, EF_true <= 40)
  + lambda_consistency * consistency(EF_pred, low_ef_logit)
```

Start with class-weighted BCE. Compute `pos_weight = N_negative/N_positive`
inside each training fold; the whole current cohort gives only an illustrative
value of 146/18 = 8.11. Compare focal loss (`gamma=1` and `gamma=2`) only as a
registered ablation because focal loss can overfit 18 positives.

Use balanced mini-batches only in training. Apply conservative spatial and
intensity augmentation to whole cines while preserving frame order. Do not use
SMOTE on frames or treat augmented copies as independent exams.

## 5. Phase and cycle correction

The current implementation smooths the LVID curve and selects its global
maximum and minimum. It does not ensure that ED and ES belong to the same
heartbeat. A long cine can therefore pair extrema from different beats or use
an artifact.

The first temporal change should be:

1. Detect candidate cardiac cycles from the ordered measurement curve or
   available phase labels.
2. Pair one ED and the following ES within each cycle.
3. Reject cycles with low endpoint confidence, implausible duration, or poor
   cycle consistency.
4. Aggregate valid per-cycle EF and low-EF scores by median.
5. Return an explicit uncertain result when no cycle passes quality criteria.

This is an AI measurement-quality output. It does not implement the separate
Readiness Gate owned by another team member.

## 6. Ordered experiments

Each row adds one factor. Do not skip directly to fusion.

| ID | Experiment | Purpose |
|---|---|---|
| L0 | Frozen current M1-LVEF3 | Reproduce the published confusion matrix and OOF predictions |
| L1 | Inner-validation operating threshold | Measure how much sensitivity can be recovered without retraining |
| L2 | Same-cycle ED/ES plus multi-cycle median | Remove phase-pairing failures |
| L3 | M1 `[T,32]` + small TCN + two heads | Test ordered geometry alone |
| L4 | Frozen EchoJEPA + small TCN + two heads | Test motion/foundation information |
| L5 | M1 + frozen EchoJEPA temporal fusion | Test complementary geometry and motion |
| L6 | Optional Gao auxiliary distillation | Test extra teacher knowledge without treating it as truth |

For L1, an alert threshold above predicted EF 40 may be evaluated while the
reference definition remains true EF <=40. For example, the released equation
maps estimated EF 42.5 and 45 to LVID ratios 0.718688 and 0.689538. These are
candidate operating points, not recommended cutoffs. They must be chosen from
inner-validation data and then frozen.

## 7. Evaluation and continuation gate

Primary low-EF metrics:

- AUPRC, with the 11% prevalence stated next to it
- AUROC
- sensitivity at specificity >=90%
- specificity, balanced accuracy, PPV and NPV at the frozen operating point
- patient-grouped bootstrap 95% confidence intervals
- reliability/calibration plot, Brier score and calibration slope/intercept

Continuous-EF safety metrics:

- MAE, RMSE, Pearson r, R2, CCC, bias and Bland-Altman limits
- EF subgroups: <=40, 40--50, 50--60 and >=60

Engineering continuation gate for the one-fold/OOF research stage:

```text
AUROC >= 0.78
sensitivity >= 0.75 at specificity >= 0.90
continuous-EF MAE <= 5.5 points
no material deterioration in the non-low-EF subgroups
```

This gate is a project decision rule, not a clinical acceptance threshold. If
L1 only moves the operating point but L3--L5 do not improve OOF AUPRC/AUROC,
the model has not gained discrimination and should not proceed to Student
distillation.

## 8. Competition presentation

The 2026 AI Innovation Award evaluates a working system rather than a model
leaderboard alone. The official rules assign the final demo 30% to functional
success, 25% to perception-decision-action integration, 25% to system design,
and 20% to commercialization/system integration.

The AI-side demo should therefore make one repeatable task explicit:

```text
PLAX cine -> LV measurement/motion evidence -> LVEF + low-EF probability
          -> confidence/uncertain status -> machine-readable AI response
```

Show raw cine, M1 landmarks/curve, selected same-beat ED/ES, continuous EF,
low-EF probability, confidence, and the reason for rejection when uncertain.
Measure task success on a locked set containing both low-EF and non-low-EF
exams. Do not present the current 93.9% accuracy alone; present sensitivity,
specificity, AUPRC and the confusion matrix.

Official competition information:

- https://ai4all.taiwanarena.tech/
- https://iuc.isu.edu.tw/storage/files/QIQsjxdHdqdNUScpoDynkyktorVGZdgqLII5W0VV.pdf

The published application deadline was 2026-07-31 17:00. As of this plan date,
this work is relevant to a team that has already registered and is preparing
for review/demo.

## 9. Immediate next action

Restore the strong-label manifest and the 164 per-exam OOF predictions before
changing code. Reproduce L0, then run the no-training L1 threshold analysis.
That result separates an operating-point problem from a representation problem
and determines whether temporal/foundation training is necessary. Formal
Teacher training and Student distillation remain prohibited until authentic
strong labels are available.
