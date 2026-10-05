# M11 completed: standalone motion diagnostic failed

All four variants completed; full status is complete,smoke=false,promoted=false.
Evaluation:82 development studies,33 low-EF. Twelve-cine smoke excluded.
Original M5 remains unchanged. No subsequent experiments automatically launched.

| Variant | Validation MAE pp | Development-test MAE pp | Low-EF MAE pp | AUROC | Screening F1 |
|---|---:|---:|---:|---:|---:|
| Fixed maps | 13.460 | 13.198 | 5.984 | 0.536 | 0.556 |
| Anatomy maps | 13.377 | 13.134 | 6.261 | 0.353 | 0.561 |
| Anatomy shuffled-time | 12.909 | 12.472 | 5.624 | 0.736 | 0.608 |
| Anatomy static-time-mean | 12.900 | 12.470 | 5.464 | 0.761 | 0.685 |
| TRAIN-median constant EF | 11.965 | 11.723 | — | — | — |

Frozen M5 context (same cohort, earlier M10 reproduction):overall MAE5.4715pp,
low-EF MAE5.2765pp,AUROC0.9635,screeningF1 0.8852. This is not a matched
input/capacity comparison. All M11 predictor variants have32,674 inference
parameters excluding the training-only projector; the external locator is extra.

## Literal numeric threshold

Predicted EF<=40 recall:0 for fixed/anatomy,17/33 for shuffled,18/33 for static.
Higher validation-threshold screening F1 must not be mistaken for numeric EF
correctness or a reliable clinical measurement.

## Strong collapse evidence

Fixed predictions:mean40.749%,SD0.021pp,range40.713..40.800%.
Anatomy predictions:mean41.036%,SD0.039pp,range40.953..41.167%.
Reference EF SD12.993pp. The ordered branches therefore make effectively
constant predictions, rather than distinguishing inter-study cardiac function.
Anatomy Pearson0.183,CCC~0.001,nonlow-EF MAE17.762pp,bias-8.095pp.
The low-EF MAE6.261pp is not evidence of successful low-EF learning: always
predicting near41 can appear decent for the low group while badly underestimating
the nonlow group. Shuffled/static predictions have SD1.946/1.734pp, still
much narrower than references.

## Prespecified diagnosis

All validation-only signal gates false. Anatomy does not beat the training-
median constant baseline by1pp; it is1.413pp worse. Anatomy-minus-static
paired validation MAE:+0.4770pp,subject-cluster95%CI[+0.0351,+0.8811].
Anatomy-minus-shuffled:+0.4683pp,CI[-0.1114,+0.9921]. No ordered-motion
benefit. Anatomy-minus-fixed:-0.0822pp,CI[-0.1547,-0.0083]; although the
interval excludes zero, magnitude fails the prespecified0.30pp gate and both
models collapse. Do not turn that tiny effect into a useful anatomy claim.

Best epochs3/3/12/15 for fixed/anatomy/shuffled/static,completed10/10/19/20
epochs with the unchanged validation-MAE/patience rule. No seed cherry-picking.

## Interpretation and next discussion

This rejects the usefulness of THIS small map encoder, teacher-supervised
objective and cached-input recipe. It does not establish that cardiac motion
in general is uninformative or that M5 is broken. Low-EF3x sampling plus Huber
and Teacher supervision can favor a central/low constant when features are weak;
global pooling/tiny from-scratch capacity may also suppress useful localized
information. Neither explanation has been isolated experimentally.

Do not continue larger versions of the same fusion or discard M5. First have
a human inspect the40 blinded TRAIN/validation previews for wall visibility,
line placement and time-axis aliasing. These are under the credentialed E:
derived directory and must not be publicly shared. No corresponding MIMIC
anatomy GT is available; visual/numeric plausibility is not segmentation accuracy.
If input quality is acceptable, a future prospectively locked diagnostic should
isolate optimization/imbalance collapse and preserve time-resolved features
before any joint-fusion claim. This requires a new protocol, not tuning on these
development-test results. No automatic follow-on run was started.

Evidence limits:single seed,study-linked weak EF,repeatedly inspected patient-
disjoint development evaluation,not external clinical validation.
