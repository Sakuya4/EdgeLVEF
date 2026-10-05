# Latest negative controls: M9–M11

The selected model remains M5-G MobileNetV3-Large. Do not describe extensions
as successfully improving the main method. All evaluations use repeatedly
inspected development studies,not independent clinical confirmation.

## M9: anatomy pooling and temporal-relation distillation

| Variant | MAE pp | Low-EF MAE pp |
|---|---:|---:|
| Matched training control | 5.388 | 5.901 |
| Anatomy-guided pooling | 5.556 | 5.587 |
| Temporal-relation supervision | 5.615 | 5.493 |
| Combined | 5.619 | 5.832 |

No improvement over matched control. Aggregate source:results/m9/summary.json.
These are separate training variants,not the frozen M5 baseline; do not select
the smallest value across experiments as if it were prospectively validated.

## M10: frozen appearance plus synthetic M-mode

| Variant | MAE pp | Low-EF MAE pp | AUROC |
|---|---:|---:|---:|
| Matched residual control | 5.463 | 5.459 | 0.964 |
| Cycle sampling only | 5.395 | 5.559 | 0.959 |
| Fixed-line motion | 5.484 | 5.380 | 0.964 |
| Anatomy-line motion | 5.484 | 5.379 | 0.964 |
| Anatomy plus cycle | 5.392 | 5.477 | 0.959 |

Best delta vs matched control:-0.0706pp,subject-cluster95%CI[-0.2758,+0.1221].
No advancement. Near-identical fixed/anatomy results do not support an anatomical
position benefit. Only~52% of development cines received a cycle proposal.
Numeric anchor plausibility~94% is not actual anatomical localization accuracy.

## M11: independent motion-map prediction

| Variant | MAE pp | Low-EF MAE pp | AUROC |
|---|---:|---:|---:|
| Fixed maps | 13.198 | 5.984 | 0.536 |
| Anatomy maps | 13.134 | 6.261 | 0.353 |
| Anatomy shuffled-time | 12.472 | 5.624 | 0.736 |
| Anatomy static-time-mean | 12.470 | 5.464 | 0.761 |
| Training-median constant prediction | 11.723 | — | — |

Ordered anatomy output collapsed around41.036%,SD0.039pp,where reference
SD was12.993pp. All validation-only signal gates failed. Do not interpret low
subgroup MAE as success when nonlow MAE17.762pp and literal low-EF recall0.

## Implication for manuscript

The main contribution should be supported accuracy/parameter evidence of the
compact spatiotemporal Student and systematic evaluation,not claims of successful
anatomical/physics-driven EF regression. Negative controls help delineate what
did not transfer. Present them in a concise table and supplement rather than
hiding them or letting them dominate the successful primary method.

Code and aggregate summaries are supplied. Restricted images,Teacher targets,
per-study predictions and weights are not. The original local failures were
implementation issues repaired before full training; they are not extra trials
or grounds for deleting the negative scientific outcomes.
