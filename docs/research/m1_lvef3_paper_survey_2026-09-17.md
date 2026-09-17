# M1-LVEF3：結果審查、LVEF 計算與 paper survey

日期：2026-09-17。檢查版本：main，`fd7833f`。
本輪只讀程式、核對既有紀錄、做數學驗證與文獻調查。
沒有修改模型／校準參數，沒有執行 M1 inference、正式 Teacher training 或 Student distillation。
這是針對問題的 focused survey，不宣稱是 systematic review。

## 1. 目前能確認哪些統計

M1-LVEF3 的來源是 `docs/models/m1-lvef3.md` 與
`models/m1_lvef3/balanced_calibration.json`。
現有 repository 沒有保存這個版本的逐 exam OOF predictions、fold manifests、
完整訓練／校準／bootstrap 程式與原始評估輸出。因此以下歷史指標是文件紀錄，
不是本次從 labels 重新算出的結果。

| 指標 | 紀錄／推導 | 狀態 |
|---|---:|---|
| Exams | 164 | 文件紀錄 |
| Reference EF≤40% | 18；10.98% | N 為文件紀錄；比例為推導 |
| MAE | 5.236 percentage points | 文件紀錄 |
| MAE 95% CI | 4.621–5.896 | 文件紀錄；本次無法核對 bootstrap 實作 |
| Bias | −1.294 points | 文件紀錄 |
| Pearson r | 0.601 | 文件紀錄 |
| CCC | 0.555 | 文件紀錄 |
| Sensitivity | 9/18=50.0%；CI 26.3–73.3% | 文件紀錄 |
| Specificity | 145/146=99.32% | 文件紀錄與分數推導 |
| F1 | 0.643 | 文件紀錄，與 counts 推導一致 |
| TP/FN/TN/FP | 9/9/145/1 | 由公開文件 counts 推導 |
| Accuracy | 154/164=93.90% | 從上述 counts 推導 |
| Balanced accuracy | 74.66% | 從上述 counts 推導 |
| PPV | 9/10=90.0% | 從上述 counts 推導，只有10個 predicted positives |
| NPV | 145/154=94.16% | 從上述 counts 推導 |
| Reference range | 25.74951–67.061752% | 校準 metadata |

高 accuracy 並不等於低 EF 篩檢好：全部預測為非低 EF，也有146/164=89.02%
accuracy。現在仍漏掉9/18個低 EF；一個 fold 漏掉全部3個低 EF。
PPV/NPV 受 cohort prevalence 影響，不能直接移植到另一族群。

**目前沒有的 M1-LVEF3 數字**：RMSE、實際 R²、AUROC、AUPRC、Bland–Altman
limits、每折完整數據、EF子群 MAE/bias、失敗率、anatomical endpoint error、
phase error、patient-level CI、實測 latency／RAM／INT8 accuracy。
`r²=0.361` 不能冒充 regression R²；固定 threshold confusion matrix也不能推算AUROC。

`checkpoints/student_v4/pooled_oof_metrics.json` 和 `low_ef_oof_metrics.json`
另保存舊 Student v4 的 RMSE=7.7595、MAE=6.0019、AUROC=0.6944等，
它們不是 M1-LVEF3 指標。M1 的 MAE 數值較低，但沒有 paired exam predictions，
不能聲稱差異具統計顯著性。

## 2. LVEF 計算是否準確：分成三層

### A. 程式是否正確執行公式：本輪已確認

File：`edgelvef/domain/interpretable_lvef.py`。
Class：`MonotonicLvefCalibration`；function：`estimate()`。
Loader：`edgelvef/infrastructure/calibration_config.py`，`load_monotonic_calibration()`。

```text
r = LVIDs / LVIDd
EF = clip(a + b * 100 * (1 - r^p), 0, 100)
a = -0.4811717786895113
b =  0.6019632205406352
p =  3.7896287594651
```

讀取實際 config/class，1001個合法 ratio 的 scalar output 與獨立 NumPy 表達式
一致，最大差2.75e−14；單調性、共同縮放不改ratio、非法值拒絕通過。
只跑既有 `tests/test_interpretable_lvef.py`，2 tests passed。
這些是 unit／數學檢查，不是 synthetic EF labels，也不是醫學 accuracy evidence。
本機既有 ONNX Python 缺torch，首次pytest無法collection；改用已存在的
`.venv-teachers` 後通過，未安裝或變更環境。
完整紀錄：`m1_lvef3_math_review_2026-09-17.json`。

### B. Formula／geometry 是否有限制：有，而且值得優先處理

**發布最終 fit 的 EF 上限只有59.58%。**
`estimate()` 允許0.20≤r<1；函數隨r下降而上升，在r=.20達到59.5800%。
即使允許r→0，極限也只有a+100b=59.7152%。外層clip(0,100)不會把它擴到100。
例如r=.50輸出55.36%、r=.70輸出44.14%、r=.90輸出19.34%。
對reference≥60%的exam，這個最終fit必然低估；metadata中最高reference
67.061752%即使得到最大可能輸出，誤差仍至少7.48 points。
**這是最終發布公式的限制，不代表歷史nested OOF每折公式都有相同上限。**
必須取得每折參數／predictions後才知道OOF子群實際表現。
不能直接把b改成1或在test上重新fit來追求漂亮結果。

**目前是單一截面縮短率的經驗校準，不是直接量EDV／ESV。**
真實mesh-derived reference應從同exam合格volume取得
`100*(EDV-ESV)/EDV`；EDV>0、ESV≥0、ESV≤EDV、單位一致、mesh品質與cycle完整
都要核對。這個volume-based定義不等於LVID ratio公式。
目前沒有原始labels，無法核對先前mesh volume／EDV／ESV產生方式。

### C. Phase／座標／confidence 是否可靠：仍未證實

File：`edgelvef/infrastructure/onnx_lvid_tracker.py`；class `OnnxLvidTracker`。
Input `[T,H,W]` → t−1/t/t+1 channels `[T,3,256,256]` → heatmaps
`[T,2,256,256]` → argmax endpoints `[T,2,2]` → raw LVID `[T]`。
`_smooth_curve()` 平滑的是**距離曲線**，不是endpoints；沒有persistent tracker。

File：`edgelvef/application/analyze_lvid_cine.py`，`analyze_lvid_cine()`。
在**整支影片**的smoothed曲線取argmax／argmin作ED／ES，没有同一heartbeat配對、
phase head、異常點排除或confidence gate。因此可能混用不同cycle或artifact extrema；
這是已確認的設計風險，不代表本次證實每支影片都如此。

`lvidd_px/lvids_px` 實際是256-grid pixels，不是original pixels或mm。
非正方形image直接stretch到256×256；固定方向且同一縮放時ratio可抵消尺度，
ED／ES方向改變時不能保證抵消anisotropic scaling。這一點需要原圖／pixel-spacing
／量測方向檢查。若改變距離定義，既有calibration不能假設仍有效。

CLI `scripts/run_m1_lvef3.py` 預設fps=50，未讀取影片fps；window依fps決定。
實際fps不同且未提供`--fps`會改變平滑時間尺度。
Confidence是heatmap peak score的幾何平均，僅報median；沒有校準或拒判。

**舊case_001的measurement.json／annotated.mp4是8-head M1，不是本2-head M1-LVEF3。**
不能把舊模型的視覺audit當成新模型的endpoint quality證據；本輪未跑新模型。

## 3. 文獻與對本專案的意義

以下皆查原始paper、作者來源或官方guideline；不同views、reference與split不直接排名。

| Paper | 已核對事實 | 對EdgeLVEF的意義 |
|---|---|---|
| [Ouyang et al., Nature 2020, EchoNet-Dynamic](https://www.nature.com/articles/s41586-020-2145-8) | Video-based、beat-to-beat EF；原研究A4C；reported MAE約4.1 points | 有序motion與多heartbeat分析值得採用；不是PLAX模型或可直接比較的cohort。 |
| [Duffy et al., JAMA Cardiology 2022, EchoNet-LVH](https://jamanetwork.com/journals/jamacardiology/fullarticle/2789370) | PLAX landmark／dimension measurement，包含獨立外部與專家對照；reported LVID MAE2.4mm | Geometry品質要用量測／解剖reference驗證，不能只看EF MAE。不能將LVH endpoint成績當EF成績。 |
| [Thomas et al., MICCAI 2022, EchoGraphs](https://arxiv.org/html/2207.02549) | Video features＋spatio-temporal keypoint graph＋EF regression／phase模块；16frame regression-head設定MAE4.01，keypoint-only4.66 | 支持geometry作auxiliary、EF另外學regression；需注意A4C與ED/ES可用性差異，不是PLAX accuracy保證。 |
| [ExoAI, Diagnostics 2024](https://pubmed.ncbi.nlm.nih.gov/39202209/) | 441patients，其中269有PLAX；landmarks→phase→geometry EF。全文Table1：對人工PLAX估值RMSE7.29/r=.89；對apical reference RMSE12.16/r=.62 | 與M1-LVEF3概念接近，證明landmark＋formula本身不是新穎性。EF<50%的reported指標也不能直接對比我們≤40%。 |
| [Gao et al., MIDL 2025](https://openreview.net/pdf?id=JEN5FzeFZj)／[MELBA 2026 extension](https://doi.org/10.59275/j.melba.2026-8194) | R(2+1)D PLAX ensemble，以proxy labels訓練、獨立report-derived295-study cohort測試；MAE6.86/r=.670；多view284-study subset fusion MAE6.37 | 最重要PLAX比較對象。應在同strong-label cohort做paired比較；不能用5.236<6.86聲稱勝過Gao。Multi-view只作survey背景，不擴大本專案scope。 |
| [EchoJEPA, arXiv 2026](https://arxiv.org/html/2602.02603v1) | Frozen backbones＋一致probe評估。Stanford EchoNet-Dynamic table：EchoJEPA-L MAE4.85、G3.97 | 支持frozen foundation probe策略；G不是本機ViT-L，A4C／multi-view結果不等於我們PLAX164exam結果。checkpoint也需核對版本。 |
| [PanEcho, JAMA 2025](https://jamanetwork.com/journals/jama/fullarticle/2835630) | Video-based multi-task system，39 interpretation tasks，內外部cohorts | EF regression與classification並行有文獻基礎，但「多head」本身不是novelty。保持本輪PLAX/LVEF範圍。 |
| [EchoXFlow, arXiv 2026](https://arxiv.org/html/2605.05447v1) | 666exams/622patients，time-resolved3D meshes與ECG；不同recording是依序取得 | 同patient可能多exam，不能只查exam split；mesh-derivedreference需品質核對，並標示same-exam但非同次acquisition的差異。 |

ExoAI數字的reference區別根據[全文Table1及Methods](https://explore.exo.inc/hubfs/Assessment%20of%20an%20Artificial%20Intelligence%20Tool%20for%20Estimating%20Left%20Ventricular%20Ejection%20Fraction%20in%20Echocardiograms%20from%20Apical%20and%20Parasternal%20Long-Axis%20Views.pdf)，
不是只讀abstract。這是本survey很重要的比較限制。

[ASE/EACVI chamber quantification 2015](https://www.asecho.org/wp-content/uploads/2025/04/2015_ChamberQuantificationREV.pdf)
指出由linear dimensions推volume依賴固定幾何假設，Teichholz／Quinones不再建議用於臨床volume計算。
此guideline不直接測試M1的自訂校準，但說明「量到diameter」不足以保證「準確global EF」。
不要用Teichholz當true label或把經驗formula改稱direct volumetric LVEF。

[CLAIM 2024](https://pubs.rsna.org/doi/10.1148/ryai.240300)與
[TRIPOD+AI 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11019967/)要求透明呈現reference、
data splits、model selection、uncertainty與evaluation流程。沒有外部資料時應清楚說明限制；
這些不是保證接受投稿的threshold，也不是所有研究都必須有prospective trial。

## 4. 是否適合投稿／比賽

在未指定venue／賽事時，以下是基於上述證據的研究判斷，非官方資格判定。

- **學生專題／工程demo競賽：可以準備。** 題目定位為「PLAX單view、輕量、
  可解釋LV systolic-function research prototype」。展示raw endpoint、curve、
  phase candidates、EF與失敗例，清楚標記development evidence。
  ONNX4MB與CPU介面是工程成果；目前不能宣稱已在i.MX93/NPU實測。
- **初步研究摘要／workshop：有條件可考慮。** 先補可重現per-exam輸出、
  split與必要baseline，按venue要求說明18positive及prior label inspection。
- **以準確low-EF篩檢為主張的完整論文：目前不建議直接送。** 50%sensitivity、
  寬CI、最終mapping高EF上限、缺少可重現評估和untouched testing都是核心缺口。
  可解釋landmark→phase→EF已有先例，還需要具體novelty与公平比較。

目前無法估計接受率或比賽名次。不存在「MAE<5.5就一定能發paper」的通用規則。
較有研究價值的定位是：**在真實mesh-derivedreference下，證明輕量有序motion
與經驗geometry有何互補、何時失效，以及如何減少low-EF／high-EF偏差。**

## 5. 建議改善順序：每次只改一項

### P0：先恢復可驗證的資料與報告

找回164exam真實EDV/ESV/LVEF、patient_id/exam_id/recording_id、影片路徑、
fold及每折OOF predictions／calibration參數。檢查samepatient全部exam同fold。
EchoXFlow總體666exam但622patients，本164subset是否有重複patient現在未知。
在每折outer-test外fit所有選擇／calibration／threshold，不能看test再選方法。
metadata明示prior label inspection；nested CV不能消除先前反覆用同cohort選設計的偏差。
未接回strong labels前不正式訓練。

補RMSE/R²/CCC/bias/LoA、AUROC/AUPRC、sensitivity/specificity/balanced accuracy、
四個EF區間的N/MAE/meanprediction/bias和patient-grouped或exam-level（無重複patient時）CI。
模型比較使用相同exam的paired bootstrap ΔMAE／ΔAUROC。所有失敗與拒判保留在cohort accounting。

### P1：先做新2-head模型的解剖／phase audit

用M1-LVEF3自身的raw endpoints、raw/smoothed curve檢查；不要沿用舊8head結果。
對照可用的EchoXFlow PLAX線段與專家endpoint／phase，量endpoint error及ED/ES frame error。
核對actualfps、image crop／aspect ratio、original-coordinate和model-grid distance差異。
這是定位問題，不能只靠更多smoothing解決。

### P2：同heartbeat配對，再做robust multi-cycle aggregation

用可用的ECG／phase annotations訓練或驗證phase識別；沒有annotatedphase不能宣稱有phase supervision。
比較現有全cineextrema和同cycle ED→ES配對＋逐beat中位數。
設計measurement-specific品質分數和可拒判狀態；這是AI measurement品質，不重訓其他組員的Readiness Gate。
避免平滑壓低真實shortening，也要報拒判coverage與剩餘cohortperformance。

### P3：解除最終calibration的表達限制，仍保留frozen baseline

在train/inner-validation上比較現在3parameterpower與低自由度、regularized monotonic spline／
train-fittedcalibration。不是手動把b拉高，也不是拿held-outtestfit。
檢查≥60%及≤40%子群；18low-EF不足以支持很多自由度或大量threshold搜尋。
純單調recalibration能改bias和40%threshold的sensitivity，但未clipped的rank不變，
不能指望它單獨改善AUROC。Geometry資訊不足時需要P4，而不是一直調公式。

### P4：Frozen foundation＋有序temporal adapter＋可選geometry

維持既定消融：T0 Gao→T1 EchoJEPA frozen probe→T2 temporal adapter→
T3經過audit的M1 features→T4可選Gao auxiliary knowledge。
每次增加一因素，smoke→1fold→continuation gate→5fold；T1failed不做T2。
EF head使用真實continuousreference；Low-EF另設classification head，threshold只在train/val選。
可比較lightweightTCN／GRU，不把cine只壓成mean/std/min/max，也不先full-finetuneViT-L。
若geometry可靠，可採EchoGraphs啟發的多task endpoint/phase＋EF learning；
graph只是候選，先用小adapter，不盲目增加複雜度。
Gao prediction只能作pseudo/KD，永不當validation/test reference。

### P5：成功Teacher後才做Student與出口

Teacher需MAE不差於currentStudent且Low-EF AUROC更高；當前M1-LVEF3缺AUROC，
不能判定已過原先continuation gate。
Teacher有效後才建立MobileNetV3-Small＋TCN/TemporalShift Student，依strong/pseudo分階段
confidence-weightedKD，雙存best_val_loss／best_low_ef_auc。
1fold有效才5fold；最終有效才ONNX/INT8 accuracy、size、CPUlatency與AI interface。
本survey不實作App、probe、acquisition guidance、i.MX93或NPU integration。

## 6. 目前結論

**目前公式的程式運算正確，但不能據此說LVEF估計準確。**
現在結果適合作為工程prototype／developmentbaseline；要主張可靠低EF辨識或高品質完整研究，
應先補reference與paired評估、修正phase／geometry證據不足及最終mapping上限，
再決定是否需要foundationTeacher。歷史結果保留，不修改指標，不用新參數覆蓋舊結果。
