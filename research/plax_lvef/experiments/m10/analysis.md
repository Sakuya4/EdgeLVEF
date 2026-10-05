# M10 completed analysis

All five variants completed. Early stopping operated as locked (patience7,
max20 epochs): control/cycle-only 11 epochs, other variants9. Smoke results
are excluded. Development evaluation:82 studies,33 low-EF studies,487 cines.

| Model | MAE (pp) | Low-EF MAE (pp) | AUROC | Screening F1 |
|---|---:|---:|---:|---:|
| Frozen M5 | 5.4715 | 5.2765 | 0.9635 | 0.8852 |
| Matched residual control | 5.4626 | 5.4591 | 0.9635 | 0.8438 |
| Cycle only | 5.3947 | 5.5587 | 0.9586 | 0.8308 |
| Fixed motion | 5.4836 | 5.3800 | 0.9641 | 0.8710 |
| Anatomy motion | 5.4839 | 5.3790 | 0.9641 | 0.8710 |
| Anatomy + cycle | 5.3919 | 5.4765 | 0.9586 | 0.8308 |

Screening F1 uses each validation-selected probability threshold, not literal
predicted EF<=40. Literal sensitivity is0.7273 and literal F1 is0.8421 for
all models (24TP,49TN,0FP,9FN). Thus none recovered the nine missed low-EF
studies at the literal threshold.

## Locked decision

No advancement. Anatomy+cycle MAE change vs matched control:
-0.0706pp, paired subject-cluster bootstrap95%CI[-0.2758,+0.1221].
Cycle-only change:-0.0678pp, CI[-0.2830,+0.1369]. Neither reaches the
prespecified0.30pp improvement or excludes zero. Fixed/anatomy motion is
slightly worse than control. Original M5 remains default.

Compared with frozen M5, the numerically best variant improves overall MAE
by0.0795pp (~1.45%) but worsens low-EF MAE by0.2000pp, lowers screening F1
and has the same literal low-EF recall. No clinical or statistical superiority
claim follows from this small change. No joint fine-tuning was launched.

## Input diagnostics and interpretation

Numeric anchor feasibility rates are93.81% train,93.21% validation,94.25%
test. These are geometric plausibility, NOT annotation-based accuracy.
Cycle proposal coverage is53.43%/53.17%/51.54%; other cines use full-cine
fallback. No reliable cache frame rate or physician phase labels available.

Cycle-only and anatomy+cycle MAEs differ by only0.0028pp. Fixed/anatomy
full-cine maps differ by only0.0003pp. The pilot therefore provides no useful
evidence that anatomy-anchored map fusion improves EF. Possible explanations
include redundant signal, inaccurate anchors/proposed cycles, weak supervision,
or suppression of a randomly initialized branch in frozen residual training.
These are hypotheses, not established failure causes.

The locator costs11.39M parameters in addition to3.21M frozen appearance;
the tiny uncertain benefit does not justify deploying this pilot graph.
Fusion parameter figures include the training-only projector and should not
be mislabeled as final deployment counts.

## Recommended next decision, not automatically launched

First audit motion-map/anchor usefulness on TRAIN/validation only, using
available manual anatomy labels and deterministic overlays; do not call numeric
coverage anatomy accuracy. To separate representation inadequacy from residual
suppression, prospectively test a motion-only EF head against matched temporal
controls, then consider motion pretraining or joint learning only if validation
signal supports it. No larger backbone, seed sweep or post-hoc test-based
hyperparameter changes are justified by these results.

All conclusions remain exploratory on a repeatedly inspected patient-disjoint
MIMIC development split with report-linked weak study EF, not external clinical
confirmation. Preserve the negative result and existing M5 checkpoint.
