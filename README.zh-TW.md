# EdgeLVEF
## 面向可攜式心臟超音波的輕量化 PLAX 影片分析

[English](README.md) · [研究方法](research/plax_lvef/METHOD.md) · [模型架構](docs/architecture.md) · [實驗成果](research/plax_lvef/RESULTS.md) · [應用程式](docs/application.md)

EdgeLVEF 以胸骨旁長軸（PLAX）超音波影片估計左心室射出分率（LVEF）。我們將大型影片 Teacher 的輸出與表徵轉移至輕量化 Student，並整合 PLAX 影像品質評估與 Linux 本地應用，朝向居家訪視、社區照護及床邊檢查的可攜式分析系統發展。

## 起源與研究思路

心臟功能反映在連續影像中的收縮與舒張變化，因此我們以影片的時空資訊作為模型設計起點。研究參考 Gao 等人的 PLAX EF 估計方法，進一步聚焦於如何將大型影片網路的分析能力轉移至適合裝置端運算的模型。相關文獻列於 [英文首頁](README.md#references)。

Teacher 由兩個 R(2+1)D-18 網路組成，用於學習影片表徵並提供訓練目標。Student 採用 MobileNetV3-Large，透過 TSM 交換相鄰影格的部分特徵，再由輕量化時序卷積整合心動資訊。訓練時同時使用報告對應 EF、Teacher EF、低 EF 軟目標與特徵配對；推論時由 Student 獨立輸出 LVEF。

## 方法特色

- 以 3.213M 參數整合影像外觀與跨影格動態資訊。
- 透過連續輸出與表徵蒸餾，連接大型 Teacher 與小型 Student。
- 固定輸入、時序模組與訓練條件，比較六種 Student backbone。
- 由獨立的 Readiness Gate 提供 PLAX 視圖、影像品質及 readiness 摘要。
- 將合法授權的 P42 取像、板內影像傳輸與 Linux 介面納入系統設計。

## 模型與系統

![Teacher–Student 模型架構](docs/assets/edgelvef-architecture.png)

圖 1.（a）離線訓練包含報告 EF、Teacher EF、低 EF 軟目標及特徵配對。（b）Student 獨立執行影片推論，Readiness Gate 提供影像條件摘要。

| 模組 | 設計 | 功能 |
|---|---|---|
| Teacher ensemble | 兩個 R(2+1)D-18；64 幀、112 × 112 | 提供 EF 與 512 維表徵監督 |
| LVEF Student | MobileNetV3-Large＋TSM＋depthwise temporal CNN；32 幀、112 × 112 | 輸出連續 LVEF 與低 EF 分數 |
| PLAX Readiness Gate | MobileNetV3-Small；五幀特徵池化、三個輸出 head | 評估視圖與影像條件 |
| 裝置端應用 | Linux UI、取像與推論介面 | 顯示超音波及分析結果 |

Student 將每幀特徵投影至 128 維，經 dilation 為 1、2、4 的殘差時序卷積後，以平均與最大池化形成 256 維影片表徵。Teacher 及訓練用特徵投影器不納入 Student 推論路徑。

## 主要成果

以下結果來自固定病人分離切分的 82 次 PLAX 檢查開發評估，其中 33 次報告對應 EF ≤ 40%。同次檢查的多段影片先各自推論，再平均為檢查層級結果。

| 模型 | 參數量 | LVEF MAE（pp） | RMSE（pp） | Pearson r | CCC |
|---|---:|---:|---:|---:|---:|
| Teacher ensemble | 62.601M | 5.635 | 7.142 | 0.848 | 0.805 |
| MobileNetV3-Large Student | 3.213M | 5.471 | 7.153 | 0.835 | 0.818 |

Student 相較 Teacher ensemble 減少 94.87% 參數。pp 為 LVEF 百分點，例如估計值 60%、參考值 55%，誤差為 5 pp。六種 backbone、低 EF 結果及另一組報告 EF 評估見 [完整成果](research/plax_lvef/RESULTS.md)。

## 閱讀與使用

![P42 與 i.MX93 裝置](docs/assets/project/probe-board-connection.jpeg)

作品說明書中的原始裝置、介面、電源、電路、PCB 與機殼圖，整理於 [圖片說明](docs/figures.md)。

研究方法與模型程式放在 [research/plax_lvef](research/plax_lvef/)，[docs](docs/README.md) 提供模組與應用說明。[edgelvef_app](edgelvef_app/) 為 Linux 應用程式，[hardware](hardware/) 收錄 i.MX93 顯示、觸控及探頭取像整合。

本次方法公開包含架構、程式與彙整統計，不提供訓練後的 LVEF 權重。受存取協議管理的影像、病人資料與逐例結果維持於受控儲存環境；探頭 SDK 與 License 使用廠商授權管道取得。
