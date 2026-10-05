# Teacher Model Card: M5-A R(2+1)D Ensemble

## Role

M5-A is the high-capacity offline Teacher. It is used to learn motion-sensitive
PLAX representations and generate training-only targets for the edge Student.
It is not required during Student inference.

## Architecture

- Two independently trained R(2+1)D-18 models.
- Kinetics-400 initialization.
- Input per cine: 64 grayscale frames repeated to three channels, 112 x 112,
  temporal stride 2.
- Encoder output: 512-dimensional feature after global spatiotemporal pooling.
- Prediction head: one linear continuous-LVEF regressor.
- Parameters: 31,300,638 per Teacher; 62,601,276 for the two-model ensemble.

The two runs use seeds `20261001` and `20261002` and different effective batch
sizes through gradient accumulation. Ensemble LVEF and representations are the
mean of the two frozen models.

## Training

- Loss: MSE against report-linked LVEF.
- Optimizer: RAdam, learning rate `1e-3`.
- Checkpoint selection: validation MAE.
- Early stopping patience: seven epochs.
- Sampling: study-balanced with threefold low-EF enrichment in training only.

## Frozen ensemble results

On the fixed patient-disjoint development test (82 studies, 33 low-EF):

| Metric | Result |
| --- | ---: |
| LVEF MAE | 5.635 pp |
| RMSE | 7.142 pp |
| Low-EF MAE | 4.224 pp |
| Pearson r | 0.848 |
| CCC | 0.805 |
| AUROC | 0.992 |
| AUPRC | 0.988 |
| Screening sensitivity | 0.970 |
| Screening specificity | 0.918 |
| Screening F1 | 0.928 |

Frame repetition increased MAE to 11.692, showing dependence on changing cine
content. Reversal increased MAE to 7.703, shuffling to 6.402 and peripheral
masking to 7.574. The masking result is a shortcut/domain sensitivity warning.

## Limitations

The Teacher is large, weak-label trained and evaluated on an internal inspected
development split. It is not an external clinical reference, and the ensemble
weights are not publicly redistributed.
