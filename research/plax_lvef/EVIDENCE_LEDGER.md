# Evidence ledger: what the manuscript may actually say

## Canonical main result

Use `results/student_mobilenet_v3_large.json` as the original Student result.
`results/m10/frozen_m5.json` is a float32 re-extraction; small numerical
differences are not a new experiment or accuracy improvement. Do not silently
mix rows from these runs or average their numbers.

| Quantity | Student M5-G | Source |
|---|---:|---|
| Deployable parameters | 3,212,755 | Student JSON |
| Test studies / low EF studies | 82 / 33 | Student JSON |
| MAE pp | 5.471303711 | Student JSON:test.mae |
| RMSE pp | 7.153044088 | Student JSON:test.rmse |
| Low-EF MAE pp | 5.276828209 | Student JSON:test.low_ef_mae |
| Pearson r / CCC | 0.835474 / 0.818261 | Student JSON:test |
| AUROC / AUPRC | 0.963513 / 0.956156 | Student JSON:test |
| Screening precision / recall / F1 | 0.964286 / 0.818182 / 0.885246 | Validation-selected score threshold |
| Literal EF<=40 accuracy / F1 | 0.890244 / 0.842105 | Student JSON:literal_lvef_le40 |
| Literal EF<=40 recall / specificity | 0.727273 / 1.000000 | 24TP,49TN,0FP,9FN |
| MAPE | 11.830528% | Relative error,not MAE |
| Within5 / within10pp | 0.634146 / 0.780488 | Student JSON:lvef_error |
| Bland–Altman limits pp | -14.886478 / +13.106879 | Student JSON:lvef_error |

MAE5.47pp means an EF estimate differs by5.47 EF units on average; it is NOT
94.53% accuracy. mAP is not a suitable substitute for continuous-EF agreement.
F1 0.885 and0.842 answer different threshold definitions and must be labelled.

## Cohort and units

Original split:379/84/82 studies,2,115/442/487 cines. Subject-disjoint.
Multiple cines are averaged to study predictions. Reports supply weak study-level
EF labels,not per-frame PLAX geometric truth. Dataset construction is not a
general claim that all MIMIC data are PLAX; this is the selected project subset.
The82-study development test has been repeatedly inspected across experiments.
Do not call it an untouched final test,external cohort,nested fivefold analysis,
or prospective clinical validation. Number of unique patients requires a verified
source; study counts cannot be relabelled as patient counts.

## Teacher comparison and discrepancy

Teacher:31,300,638 parameters per model; two-model ensemble62,601,276.
Normal stress-analysis result:`results/teacher_ensemble_stress.json:modes.normal`:
MAE5.634563398,low-EF MAE4.223939517,AUROC0.991960421,F1 0.927536232.
`results/bootstrap_intervals.csv` reports Teacher AUROC0.993197279 instead.
This is an unresolved analysis-source discrepancy: retain both sources, use
normal-stress AUROC0.991960 for the main paired descriptive table, and do not
attach an interval from a different score calculation without checking provenance.

Student minus Teacher MAE:-0.163259687pp,paired95%CI[-1.043125031,+0.709632985].
The interval supports neither superiority nor a formal noninferiority conclusion:
no prospective noninferiority margin/test was specified. Verify whether original
CI resampling is study- or subject-clustered before labelling it patient-level.
Reduction in parameters:~89.74% versus one Teacher,~94.87% versus ensemble.
Neither is a measured latency,power,FLOP or NPU speedup.

## Claim inventory

| Claim | Status | Permitted wording |
|---|---|---|
| Compact PLAX cine LVEF regression | Supported internal development | Feasible compact model on this selected cohort |
| Six Student backbone comparisons | Supported | Controlled benchmark,see original CSV |
| Teacher-like overall MAE with fewer parameters | Descriptive supported | Favorable trade-off;not formal clinical equivalence |
| Improved low-EF MAE over Teacher | Unsupported | Teacher has lower low-EF MAE |
| Anatomy and motion improved M5 | Unsupported | M9–M11 failed prespecified signal/advancement gates |
| Fully interpretable geometric/Simpson EF | Unsupported for M5 | Learned regression;M1 is a separate measurement baseline |
| Calibrated uncertainty | Not established | Low-EF soft target is heuristic,not calibrated confidence |
| Superior to published models on other datasets | Not established | Context comparison only;different samples/labels |
| i.MX93 real-time/NPU/INT8 fidelity | Not established here | Deployment candidate;hardware evaluation pending |
| Clinical safety/external generalization | Not established | Requires independent clinical/device validation |
| Q1 acceptance or first/novel architecture | Not established | Target ambition,not scientific result |

Do not make the old unvalidated `volume_curve` output a measurement or a
supervised anatomical explanation. M10 locator costs11.39M additional parameters;
M11 predictor32,674 excludes that locator. A paper cannot hide preprocessing cost.

## Missing submission evidence

Independent external/patient cohort,larger number of unique low-EF subjects,
multiple prespecified training seeds,device calibration,measured board latency/
memory/power,INT8 agreement,and verified ethics/DUA/institutional statements.
Missing items should be visible in a gap list,not invented by the writing AI.
