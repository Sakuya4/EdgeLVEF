# M10: anatomy-anchored synthetic M-mode fusion

Locked before training, 2026-10-05. This is a development mechanism pilot,
not independent clinical confirmation. M5 stays frozen and remains the default.

## Scientific question

Does a local position-by-time motion representation add EF information beyond
the successful M5 appearance/TSM representation? M9 auxiliary mask/temporal
relation losses did not improve the matched control; adding another loss alone
is not sufficient evidence of useful motion learning.

Synthetic M-mode is prior art, not our invention:
[Ozkan et al., GCPR 2023](https://arxiv.org/abs/2309.03759).
Cardiac phase information is motivated by
[EchoPhaseNet](https://doi.org/10.1002/mp.17733), but its phase labels/results do
not establish PLAX phase accuracy here. Novelty of the proposed combination
requires further literature comparison and positive controlled results.

## Cohort and supervision

Use the unchanged M5 index: 2,115/442/487 cines from 379/84/82
train/validation/test studies. Assert subject-disjoint splits and consistent
study EF. MIMIC report-linked study EF is weak supervision, not frame-specific
or PLAX-derived geometric EF ground truth. The test cohort has already informed
earlier research and must be called repeatedly inspected development evaluation.
No EchoNet-LVH test, Gao, or EchoXFlow tuning. Restricted caches/checkpoints and
predictions remain under the credentialed E: derived directory.

## Inputs and mechanisms

Frozen M5 MobileNetV3-Large + TSM produces 256-D features, EF, low-EF logit
from 32 uniform frames. Frozen M1 ResNet18-FPN localizes diameter endpoints on
64 uniformly spaced frames using its original adjacent-frame triplets and
ImageNet channel normalization at 256 pixels. Average the two phase-specific
LVID endpoint heads; this is an operational locator proposal, NOT validated
phase-independent anatomy. Input is the existing 112-pixel cache upsampled for
the locator; this cannot recover lost spatial detail or support new mm accuracy.

Anchors stay fixed across time: median endpoint coordinates over valid frames.
Five parallel lines at offsets -12/-6/0/6/12 pixels sample an 80-pixel spatial
extent and 128 time samples, preserving displacement amplitude. Motion maps
are 5x80x128. Invalid anchors use the prespecified central vertical lines,
with fallback frequency reported rather than excluded studies.

Diameter proposals are smoothed with a five-sample box filter. Period proposal
requires a local autocorrelation peak >=0.5 at lag 8..32, diameter range >=2
pixels, and two peaks separated by that lag (+/-20%, minimum tolerance 2).
No reliable cache frame rate: this is sample-domain periodicity, not a
physiological timing guarantee. Missing complete-cycle proposals keep full cine.
These are NOT physician ED/ES labels. Report cycle coverage.

Before training, >=70% of frames must have plausible anchors (length 8..70px,
coordinates 8..104px) in >=70% of train and validation cines; otherwise stop
the scientific run and record input feasibility failure. This is only numeric
plausibility, not anatomical correctness. No EF-based input filtering.

## Locked comparisons

1. Frozen original M5, recomputed on the same cohort.
2. Control: frozen full-cine M5 features + residual fusion head, zero motion slots.
3. Cycle only: frozen M5 cycle-window features + identical head, zero motion slots.
4. Fixed motion: full-cine M5 + central-line motion maps.
5. Anatomy motion: full-cine M5 + median-LVID-anchored maps.
6. Anatomy cycle: cycle-window M5 + anchored cycle maps.

Motion CNN: Conv3x3 stride2 5->16->32->64, GroupNorm/Hardswish,
global pooling. Concatenate 64-D motion with 256-D appearance, Linear320->128,
Hardswish/dropout0.2, two residual scalar heads. Zero initialization preserves
M5 predictions before optimization. Control fusion capacity is matched; motion
encoder is disabled. Include frozen appearance and locator parameter costs in
total deployment reporting; this large frozen locator is a pilot, not yet an
edge deployment achievement.

## Optimization and selection

Same seed 20261005, max20 epochs, batch32, AdamW lr3e-4/decay1e-4,
cosine schedule, gradient clip1, validation-MAE selection, patience7.
Study-balanced replacement sampling; low EF weight3. Frozen appearance feature
caching means image augmentations cannot retrain M5. Motion maps receive shared
gain0.9..1.1/offset-0.04..0.04, no temporal permutation or amplitude normalization.
Loss: Huber(report, delta5) +0.5 Huber(frozenTeacher) +0.2 BCE(Teacher low
probability) +0.1 cosine(projected combined feature, frozenTeacher embedding).
This retains original M5-E objective weights; only fusion/motion parameters learn.
No joint encoder fine-tuning in this run; it needs a subsequent prospectively
locked experiment, not adaptation based on development test performance.

## Statistics and decision

Study-mean cine predictions. Report MAE/RMSE in EF percentage points, MAPE
separately, bias, Pearson/CCC, Bland-Altman, within5/10 rates, AUROC/AUPRC,
validation-selected screening threshold and literal predicted-EF<=40 metrics.
Paired subject-cluster bootstrap2500 for MAE change vs matched control.
Advancement requires MAE improvement >=0.30pp, paired95% upper bound<0,
low-EF MAE deterioration<=0.30pp, literal sensitivity deterioration<=0.05.
All results and failures retained. An advancement is development evidence only;
do not claim clinical equivalence or change gates after observing results.

## Reproduction

Run `scripts/run_m10_motion_fusion.ps1`: unit tests -> isolated one-epoch smoke
-> input extraction/diagnostics -> five variants -> comparison.
Caches are resumable by row, checked against index/checkpoint hashes. No automatic
heartbeat or future experiments. Human will report when terminal completes.
