# Spatiotemporal Teacher ensemble

The Teacher provides high-capacity PLAX video supervision during model development.

| Property | Specification |
|---|---|
| Ensemble | Two independently trained R(2+1)D-18 networks |
| Input | 64 grayscale frames repeated to RGB |
| Resolution and sampling | 112 × 112; temporal stride 2 |
| Representation | 512-D global spatiotemporal feature |
| Prediction head | Linear continuous-EF regression |
| Parameters | 31,300,638 per model; 62,601,276 total |
| Initialization | Kinetics-400 |
| Learning objective | MSE against report-linked EF |
| Optimizer | RAdam; learning rate 1 × 10⁻³ |
| Checkpoint selection | Validation MAE |
| Ensemble targets | Mean EF estimate and mean encoder representation |

The two training runs use seeds 20261001 and 20261002 and effective batch sizes 16 and 32. Study-balanced sampling gives low-EF training studies additional weight.

The ensemble achieves MAE 5.635 pp, RMSE 7.142 pp, Pearson r 0.848 and CCC 0.805 on the 82-study development benchmark. [Results](RESULTS.md) includes low-EF metrics and controlled temporal-input assessments.

Architecture is defined by `GaoCineRegressor` in `src/plax_lvef/study_video.py`, with the importable equivalent `GaoR2Plus1DTeacher` in `edgelvef.research`. Trained ensemble weights remain in access-controlled storage.
