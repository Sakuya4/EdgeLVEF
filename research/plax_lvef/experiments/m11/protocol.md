# M11: does the cached motion representation carry EF information?

Locked before outcomes,2026-10-05. Diagnostic, NOT automatic model promotion.
M10 motion fusion failed the prespecified advancement gates. This experiment
tests the representation independently of frozen appearance residual correction.
No new claimed invention or clinical equivalence. Synthetic M-mode rationale:
[Ozkan et al., GCPR2023](https://arxiv.org/abs/2309.03759).

## Controlled comparisons

| Variant | Input | Question | Expected if component matters |
|---|---|---|---|
| Fixed | Five full-cine central lines | Motion maps without anatomical anchoring | Provides natural spatial control |
| Anatomy | Five full-cine median-anchor lines | Does a standalone map learner predict EF? | Beats training-median constant predictor |
| Shuffled | Anatomy maps, deterministic shared time-column permutation | Does temporal order add signal? | Worse than ordered anatomy maps |
| Static | Anatomy time-mean repeated over time | Does variation add signal over static appearance? | Worse than ordered anatomy maps |

One stable permutation per cine, independent of EF/split, shared across all
lines. Static input keeps the same shape and spatial time-mean, removes temporal
variation. All variants use identical architecture, initialization seed,
optimization, supervision and selection; only inputs differ. No appearance
features, M5 scalar EF/logit or physiology ratios enter the predictor.
Teacher prediction/embedding are used only as training supervision, not input.

## Data and privacy

Reuse completed, unchanged M10 cache and original patient-disjoint M5 index:
2,115/442/487 cines from379/84/82 studies. Validate cache signature and splits.
No new imaging extraction needed. Source is112-pixel cache: cannot restore
full-resolution anatomy. Weak study-level report-linked EF is not per-cine
PLAX geometric EF truth. Existing inspected test is development evaluation,
not an untouched external test. Gao/EchoXFlow/LVH test stay unused.

Restricted checkpoints/predictions/previews remain under credentialed E: derived.
Forty blinded previews (20 TRAIN,20 validation), selected evenly over index
without EF/outcome filtering, show original start/middle/end frames with sampling
lines and maps. Do not use test previews to tune. Plausibility/motion-map
differences are not clinician-verified accuracy. Available LVH manual masks do
not label these MIMIC cines; no Dice or anatomical accuracy can be inferred.

## Architecture and training

Conv3x3 stride2 5->16->32->64 with GroupNorm4/Hardswish; global pool;
64->128 Hardswish/dropout0.2; separate EF and low-EF scalar heads. EF output
scaled by unweighted TRAIN study mean/std. Training-only64->512 projector for
Teacher feature supervision; exclude it from inference parameter count. Include
external locator cost separately when discussing the whole system.

Seed20261005, AdamW lr3e-4/weight_decay1e-4, cosine,max20 epochs,
patience7, batch32, clip1. Study-balanced replacement sampling, low EF weight3.
Gain0.9..1.1 and offset-0.04..0.04 shared over the map. M5-E/M10 loss weights:
Huber(report,delta5)+0.5Huber(TeacherEF)+0.2BCE(Teacherlowprob)+
0.1cosine(projectedFeature,TeacherFeature). No sweeps, new seeds, or threshold
changes after results. Select checkpoint by validation study-level MAE only.
Freeze all four selections before computing any test metrics.

## Diagnosis, not efficacy gates

Validation-only prespecified signals:

- Predictive signal: anatomy MAE beats TRAIN-median constant predictor by>=1pp.
- Ordered-motion signal: anatomy beats BOTH shuffled/static controls by>=0.5pp
  and upper paired subject-cluster bootstrap95%CI<0 for both.
- Anatomical-position signal: anatomy beats fixed by>=0.3pp and paired upperCI<0.

2500 bootstrap samples, fixed seed. Failure of these gates is not proof that
motion in general is unhelpful; it concerns this map/encoder/supervision recipe.
Single seed, correlated comparisons: exploratory, not confirmatory multiplicity-
adjusted clinical evidence. No further training is automatically triggered.

## Reporting

MAE/RMSEpp, low-EF MAE, bias, Pearson/CCC, MAPE separately, within5/10,
Bland-Altman, AUROC/AUPRC, validation-selected screening metrics AND literal
predicted EF<=40 metrics. Compare with frozen M5 reference from M10 (MAE5.4715,
low-EF MAE5.2765pp) as context, not a matched parameter/input fairness claim.
Retain all negative results. The aim is to decide if motion-only pretraining or
joint fusion is justified, not to ship this diagnostic model regardless of outcome.

## Run

`scripts/run_m11_motion_diagnostic.ps1`: unit tests -> isolated1-epoch smoke
-> previews -> four training variants -> frozen evaluation -> comparisons.
Full output: E:/MIMIC-IV-Echo-1.0.1/derived/m11_motion_diagnostic_20261005.
No external push or heartbeat.
