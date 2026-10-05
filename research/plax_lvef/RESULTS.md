# Aggregate Results

## Primary Teacher–Student comparison

| Model | Params | MAE pp | Low-EF MAE pp | Pearson | CCC | AUROC | AUPRC | Screening F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M5-A two-Teacher ensemble | 62.60 M | 5.635 | **4.224** | **0.848** | 0.805 | **0.992** | **0.988** | **0.928** |
| M5-G MobileNetV3-Large Student | **3.21 M** | **5.471** | 5.277 | 0.835 | **0.818** | 0.964 | 0.956 | 0.885 |

The Student has the lower MAE point estimate, but its paired MAE interval versus
the Teacher crosses zero. The Teacher retains stronger low-EF MAE and screening
ranking. The defensible conclusion is an accuracy-efficiency trade-off, not
Student superiority.

## Controlled Student backbone ablation

| Backbone | Params | MAE pp | Low-EF MAE pp | AUROC | Screening F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MobileNetV3-Small | 1.12 M | 6.645 | 6.012 | 0.938 | 0.811 |
| ShuffleNetV2-1.0 | 1.50 M | 6.879 | 7.986 | 0.936 | 0.829 |
| MobileNetV2 | 2.51 M | 6.414 | 5.133 | 0.955 | 0.862 |
| **MobileNetV3-Large** | **3.21 M** | **5.471** | 5.277 | 0.964 | **0.885** |
| EfficientNet-B0 | 4.29 M | 5.857 | **4.882** | **0.967** | 0.857 |
| ResNet-18 | 11.35 M | 5.689 | 5.217 | 0.960 | 0.845 |

MobileNetV3-Large is selected for the best overall MAE and favorable parameter
count. EfficientNet-B0 is the strongest low-EF-MAE alternative but has 34%
more parameters and worse overall MAE.

## Evidence boundary

All values are aggregate internal development results using report-linked weak
LVEF labels. The test cohort has been inspected repeatedly during the research
program and must not be represented as a final untouched test set. No patient
identifiers or per-study predictions are included here.
