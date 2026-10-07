# Aco P42 × FRDM-i.MX93：板內 Headless Android Sidecar

2026-10-07 成果快照；**已驗證即時取像與開機自動連線，尚未完成穩定性驗收**。
研究用途，非醫療診斷產品。本資料夾與既有 Linux App 分開保存，不會自動部署或覆寫它。

唯一允許架構：

```text
Aco P42 (Wi-Fi Direct group owner)
  → 同一塊 FRDM-i.MX93 的 Android 12 headless runtime / 官方 Aco AAR
  → 板內 Unix socket (/run/aco-ipc/frame.sock)
  → 原生 Linux GTK EdgeLVEF App
```

不得使用外接 Android Companion、手機、平板或外部即時影像轉送。
開發電腦只用於部署與診斷。完整限制見 [AGENTS.md](AGENTS.md)。

## 目前成果與限制

- 板內 ARM64 Android、Binder、IW612 Wi-Fi Direct、合法 SDK License IPC 已串接。
- Linux App 已實際接收／解碼／顯示 P42 影像，觀察約 6–7 FPS。
- systemd 監督開機啟動、程式退出後重新啟動與重新送入板上私密 License。
- 2026-10-07 重連優化將固定 30 秒節流改為 2 秒退避／20 秒總逾時，並以
  socket identity 修正同 PID Service 重啟後的 License 重送；受控上板測試約
  13–17 秒恢復串流，詳見 [RECONNECT_OPTIMIZATION_20261007.md](RECONNECT_OPTIMIZATION_20261007.md)。
- 自動握手成功紀錄包含通道 161 與 48；通道 161 的單一統計不能代表所有握手。
- 曾在約 282 秒／1,985 張與 214 秒／861 張後停止傳輸。不是穩定性通過。
- 已觀察群組斷線在先，約 45–60 秒後 Android 出現未處理的網路例外
  (`ENETUNREACH` / OkHttp)。例外不是這些案例最初斷線原因的證明。
- 探頭曾自行關機；充飽電後也需要繼續對照燈號、訊號、CPU 與群組狀態。
- 壓力測試初期 CPU 約 82–93%，訊號約 −63 至 −52 dBm；目前只是線索，
  不能宣稱 CPU、距離或電量已被證明是唯一原因。
- 沒有完成完整 30 分鐘壓測結論；Readiness Gate／LVEF inference 也未完成本次驗收。

## 內容

- `sidecar/aco-connector/`：Android Service、Unix JPEG frame server、私密 License IPC。
- `sidecar/runtime/`：OCI 設定產生器、板內 supervisor、啟動腳本與受限手動重播。
- `sidecar/wifi-hal/`、`sidecar/wifi-supplicant/`：Android Wi-Fi 相容層原始碼／設定。
- `sidecar/linux/`：本機影像協定、診斷、隱私篩選與壓力測試採樣工具。
- `sidecar/linux-app/`：已在板上使用的取像／UI 整合快照；不是對新版 App 的自動 patch。
- `tools/`：COM3 部署、私密 License 匯入、核心／驅動重建工具。
- `kernel/config.aco-sidecar`：已使用的核心設定；不附核心或模組二進位檔。
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md)：環境、建置依賴與部署注意事項。
- [RECONNECT_OPTIMIZATION_20261007.md](RECONNECT_OPTIMIZATION_20261007.md)：
  重連狀態機、失敗實驗、雜湊與實機時序。

## 私密與第三方檔案

官方 AAR、Android rootfs、交叉編譯器、第三方完整原始碼、APK、核心二進位、
License、原始日誌與超音波影像**都不在這次提交內**。請合法取得依賴。
License 只放在 Git 外的私密檔案，以板內 IPC 送入，不得嵌入 APK 或輸出日誌。
忽略規則只是額外防護，不取代提交前的私密資料檢查。

目前板端私密 License 位置是 `/var/lib/aco-sidecar/secrets/p42.license`，
目錄 0700、檔案 root:root 0600；Android 不掛載這份檔案。

## 壓力測試

`sidecar/linux/stress_capture_safe.py` 在板內最多記錄 30 分鐘，約每 5 秒採樣
群組／Android PID／UI 計數與 FPS／CPU／可用記憶體／訊號／傳輸統計。
核心斷線事件保存 boot-monotonic 時間；UI 的日誌約每 10 秒一次，**不是逐幀延遲量測**。
UTC 對時使用開發電腦的診斷時間錨，容許序列部署延遲；板上日曆時鐘曾不正確。

先固定距離正常試量，再一次只更改距離；每次記錄實際距離、移動時間與探頭燈號。
斷線後不要立刻重啟，以保留故障現場。先區分探頭關機、無線群組消失、SDK 程式
退出，以及群組仍存在但取像卡頓。缺少證據時必須保留未知，不自動降級架構。
