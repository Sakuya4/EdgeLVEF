# Low-LVEF academic, engineering, and oral-defense strategy

Date: 2026-09-17

## What can cause the current result

The present development result has 18 low-EF exams among 164 exams. Sensitivity
is 9/18 while specificity is 145/146. This supports the observation that the
operating point is conservative. It does not by itself prove why.

Test the following hypotheses in this order:

| Hypothesis | Evidence to inspect | Corrective action |
|---|---|---|
| Too few low-EF labels | positive count per patient/fold | obtain more authentic strong-label low-EF exams; balance training batches only |
| Spectrum bias | EF histogram and low-EF severity distribution | report subgroups; enrich training without altering validation prevalence |
| Site/device shift | MAE, bias and sensitivity by site/vendor | train-only domain augmentation; site-balanced sampling; external test |
| Reference mismatch | compare mesh-derived EF, report EF and timing | name the reference explicitly; do not merge incompatible GT silently |
| Wrong ED/ES selection | false-negative cine and selected frame audit | same-heartbeat pairing and multi-cycle median |
| Diameter-only limitation | good endpoints but wrong EF | add ordered frozen EchoJEPA motion features and a direct LowEFHead |
| Calibration/threshold issue | ranking is acceptable but cutoff misses cases | inner-validation calibration and frozen alert threshold |
| Regression to the mean | subgroup bias: low EF overestimated, high EF underestimated | weighted multitask learning and subgroup monitoring |

## Academically defensible correction

1. Restore patient IDs, authentic EDV/ESV/LVEF, fold membership and OOF
   predictions.
2. Lock a patient-grouped outer split before model changes.
3. Keep natural prevalence in validation/test.
4. In training only, use positive-aware batches and fold-specific class weight.
5. Compare one factor at a time:
   current M1, threshold calibration, same-cycle aggregation, M1-TCN,
   EchoJEPA-TCN, then fusion.
6. Retain continuous EF and add a separate probability for GT LVEF <=40%.
7. Use Gao only as auxiliary knowledge, never as GT.
8. Report MAE/RMSE/CCC/bias/Bland-Altman and AUROC/AUPRC/sensitivity/
   specificity together with patient-grouped confidence intervals.
9. Confirm any selected method on an untouched cohort.

Synthetic EF, Teichholz EF, Gao EF and pseudo labels cannot repair missing
strong labels. They may support pretraining or distillation but cannot enter
validation or support an accuracy claim.

## Engineering correction

The first production-oriented candidate is:

~~~text
M1 sequence [T,32] + frozen EchoJEPA sequence [T,D]
        -> small TCN
        -> continuous EF head
        -> low-EF probability head
        -> uncertainty/coverage output
~~~

Before training this candidate, correct phase handling by pairing ED with the
following ES in the same heartbeat and taking the median across acceptable
cycles. Preserve raw output for audit. When no cycle passes confidence and
consistency checks, return uncertain instead of a confident normal result.

A threshold-only adjustment is an inexpensive baseline. It may increase
sensitivity by accepting more false positives, but it does not improve AUROC
or AUPRC. It is successful only if a frozen threshold performs on held-out
data.

## Stop conditions

Do not continue to Student distillation unless a Teacher or fusion candidate
meets all project gates:

- AUROC at least 0.78
- sensitivity at least 0.75 at specificity at least 0.90
- continuous-EF MAE no worse than 5.5 percentage points
- no material deterioration in the non-low-EF groups

These are engineering research gates, not clinical certification criteria.

## Oral-defense story if sensitivity cannot be repaired in time

Do not call the model clinically ready and do not hide the false negatives.
A defensible story has four parts.

1. Problem: PLAX-only edge inference is useful where complete apical acquisition
   is unavailable, but reduced EF is rare and safety-critical.
2. Contribution: the work built an interpretable, four-megabyte endpoint model,
   deterministic LVID trajectory, explicit EF mapping, reproducible exam-level
   evaluation, and an AI-side uncertainty contract.
3. Finding: average EF error was promising in development, while only half of
   the 18 low-EF exams were detected. The failure analysis showed why overall
   accuracy was misleading and identified data scarcity, cardiac-phase pairing
   and diameter-only representation as the next limits.
4. Safety and future work: the system remains research decision support. It
   rejects uncertain studies, exposes measurement evidence, and requires
   patient-grouped external validation before clinical claims.

Suggested short answer:

> Our objective was not to turn one PLAX diameter into unquestionable clinical
> EF. We tested whether an interpretable edge model could provide measurable LV
> systolic-function evidence. It achieved a development MAE of 5.236 points, but
> the low-EF cohort contained only 18 exams and sensitivity was 50%. We therefore
> report the limitation directly, retain a high-confidence research interface,
> and use the failure analysis to motivate same-beat temporal modeling,
> low-EF-aware supervision and external validation. The contribution is the
> auditable pipeline and the evidence showing where a geometry-only model stops
> being sufficient.

This story is credible only when accompanied by the full confusion matrix,
confidence intervals, failure examples and a statement that the evidence is
developmental.
