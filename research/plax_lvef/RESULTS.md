# LVEF estimation and model efficiency

## Evaluation design

The primary benchmark uses the selected MIMIC-IV-ECHO PLAX subset with patient-disjoint training, validation and development-test partitions. The development-test partition contains 82 studies, including 33 with report-linked EF ≤ 40%. Multiple eligible cine predictions are averaged within each study.

All EF errors below use percentage points (pp). The screening head uses a validation-selected score threshold; numerical low-EF analysis uses `estimated EF ≤ 40%`.

## Teacher and selected Student

| Model | Parameters | MAE (pp) | RMSE (pp) | Low-EF MAE (pp) | Pearson r | CCC |
|---|---:|---:|---:|---:|---:|---:|
| R(2+1)D-18 Teacher ensemble | 62.601M | 5.635 | 7.142 | 4.224 | 0.848 | 0.805 |
| MobileNetV3-Large Student | 3.213M | 5.471 | 7.153 | 5.277 | 0.835 | 0.818 |

Student parameter count is 94.87% lower than the ensemble. The Student-minus-Teacher paired MAE difference is −0.163 pp, with bootstrap 95% CI [−1.043, 0.710].

![EF error estimates and bootstrap intervals](../../docs/assets/ef-error-intervals.png)

## Six-backbone comparison

Input sampling, temporal module, distillation objective, split and evaluation are held fixed.

| Student backbone | Parameters | MAE (pp) | Low-EF MAE (pp) | AUROC | Screening F1 |
|---|---:|---:|---:|---:|---:|
| MobileNetV3-Small | 1.118M | 6.645 | 6.012 | 0.938 | 0.811 |
| ShuffleNetV2-1.0 | 1.503M | 6.879 | 7.986 | 0.936 | 0.829 |
| MobileNetV2 | 2.506M | 6.414 | 5.133 | 0.955 | 0.862 |
| MobileNetV3-Large | 3.213M | 5.471 | 5.277 | 0.964 | 0.885 |
| EfficientNet-B0 | 4.289M | 5.857 | 4.882 | 0.967 | 0.857 |
| ResNet-18 | 11.354M | 5.689 | 5.217 | 0.960 | 0.845 |

MobileNetV3-Large has the lowest overall MAE among the six Student backbones. EfficientNet-B0 provides an alternative with lower low-EF MAE and 34% more parameters.

![Six Student backbones: parameter count and EF error](../../docs/assets/student-backbone-comparison.png)

## Student EF agreement

| Metric | Value |
|---|---:|
| MAE | 5.471 pp |
| Median absolute error | 4.207 pp |
| RMSE | 7.153 pp |
| Mean bias | −0.890 pp |
| MAPE | 11.831% |
| Error within 5 pp | 63.4% |
| Error within 10 pp | 78.0% |
| Bland–Altman lower limit | −14.886 pp |
| Bland–Altman upper limit | 13.107 pp |
| Pearson r | 0.835 |
| CCC | 0.818 |

## Student low-EF analysis

| Metric | Screening head | Numerical EF ≤ 40% |
|---|---:|---:|
| Precision | 0.964 | 1.000 |
| Recall | 0.818 | 0.727 |
| Specificity | 0.980 | 1.000 |
| F1 | 0.885 | 0.842 |
| Accuracy | 0.915 | 0.890 |
| AUROC | 0.964 | — |
| AUPRC | 0.956 | — |

The screening column uses the validation-selected threshold 0.443195. The numerical rule yields 24 TP, 49 TN, 0 FP and 9 FN. These are two distinct output rules.

## Separate report-EF reassessment

The project description also reports a second set of 54 studies, including 17 with EF ≤ 40%. This set is presented separately from the 82-study benchmark.

| Metric | Teacher | Student |
|---|---:|---:|
| MAE (pp) | 8.832 | 9.409 |
| Low-EF MAE (pp) | 11.485 | 12.792 |
| Numerical EF ≤ 40% recall | 0.824 | 0.647 |
| Numerical EF ≤ 40% F1 | 0.848 | 0.688 |
| Error within 10 pp | 66.7% | 64.8% |

Source: *EdgeLVEF 作品說明書 4.0*, Sections 5.1 and 5.4, 2026-10-14.

## Temporal-input analysis

The frozen Teacher ensemble is evaluated after controlled changes to cine content.

| Teacher input | MAE (pp) |
|---|---:|
| Original sequence | 5.635 |
| Repeated frame | 11.692 |
| Reversed order | 7.703 |
| Shuffled order | 6.402 |
| Peripheral masking | 7.574 |

## Numerical sources

[Student summary](results/student_mobilenet_v3_large.json), [backbone comparison](results/backbone_ablation.csv), [bootstrap intervals](results/bootstrap_intervals.csv), and [Teacher input analysis](results/teacher_ensemble_stress.json) provide the aggregate values.

Teacher AUROC is 0.991960 in the original temporal-input analysis and 0.993197 in the bootstrap table. Each is retained with its source; the main Teacher–Student table reports continuous EF metrics common to both sources.
