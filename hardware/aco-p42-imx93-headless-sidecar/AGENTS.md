# Aco P42 Integration — Non-negotiable Architecture

本專案的唯一允許目標：

Aco P42
→ FRDM-i.MX93 上的 headless Android Sidecar
→ 本機 IPC
→ FRDM-i.MX93 Linux EdgeLVEF App

## 絕對限制

- 禁止使用外接 Android 手機、平板或 Android 模組。
- 禁止將 Android Companion 作為 fallback、暫時方案或 Demo 方案。
- 禁止把即時影像先送到外部電腦、手機或雲端再傳回 i.MX93。
- 開發電腦只能用於 serial、SSH、部署與診斷，不得成為執行期元件。
- EdgeLVEF、Readiness Gate、LVEF inference、UI 必須原生執行於 i.MX93 Linux。
- Aco 官方 Android AAR 必須執行於同一塊 i.MX93 內的 headless Android runtime。
- Android 與 Linux 間只允許板內 IPC，例如 Unix socket、shared memory 或 localhost。
- 使用合法 License；禁止繞過、破解或自行偽造 License 驗證。
- License 不得寫入 Git、原始碼、APK、測試輸出或日誌。

## 禁止自動降級

若 Sidecar、Binder、IW612 Wi-Fi Direct、Android Wi-Fi HAL 或 Aco SDK 無法運作：

1. 不得改用外接 Android Companion。
2. 不得擅自改變產品架構。
3. 必須保留錯誤輸出與實驗結果。
4. 必須報告確切阻塞層級及下一個同架構內的修正方案。
5. 若確實無法繼續，停止並要求使用者決策。
