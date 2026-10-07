# 重建與部署範圍

這是已上板原始碼快照，不是無依賴的一鍵安裝包。先閱讀 README 和 AGENTS。

## 已測試環境

- FRDM-i.MX93、2 GB RAM、IW612；Linux
  `6.6.36-lts-next-gab2a7006a738-aco-sidecar`，BinderFS／PSI 啟用。
- Android 12 ARM64 headless OCI runtime；`runc` 與 Android rootfs 需另外取得。
- 核心原始碼固定提交 `d23d64eea5111e1607efcce1d601834fceec92cb`。
- NXP mwifiex `lf-6.6.36-2.1.0`，固定提交
  `e5c9a169d7b7a441a20d2cf10a9752e249b71cff`。
- Gradle 8.4、Android SDK compileSdk 34、minSdk 26；官方
  `com.aco.ultrasound-release-1.0.4.aar`，僅 ARM64 ABI。

## Android 建置

合法取得官方 AAR，放在
`sidecar/aco-connector/app/libs/com.aco.ultrasound-release-1.0.4.aar`（Git 忽略）。
在 `sidecar/aco-connector` 使用 Gradle 8.4 執行 `:app:assembleDebug`。
此快照未附 Gradle wrapper／SDK／AAR；公開快照不能單獨完成 Android 建置。

## 核心與 Wi-Fi 重建

`tools/wsl_build_sidecar_kernel.sh` 與 `wsl_build_iw612_sidecar_modules.sh`
保留原工作機的建置路徑；在新環境先調整／提供對應原始碼、工具鏈、baseline config。
HAL 建置腳本需合法的 Android 12 `libhardware_legacy` 標頭，預期在
`vendor/aosp-libhardware-legacy-android12/include`；第三方內容不附在此快照。
`kernel/config.aco-sidecar` 是已測試核心設定，不是二進位檔。
不要直接執行未核對路徑的部署腳本；不用修改既有 Linux App 來驗證建置。

## 板內部署

runtime 檔案以 `/opt/aco-sidecar`、Android eMMC bundle 與 `/run/aco-ipc`
為目標；腳本內保留原實測板的絕對路徑。部署前核對 rootfs、掛載、核心版本與
package UID。原 Linux AP／DHCP 與另一個 Wi-Fi 管理程式不得同時搶用 IW612。
目前參數預設 `host_mlme=1`、TW 國碼、`ps_mode=2`、`auto_ds=2`、`fw_reload=0`。
`fw_reload=1` 曾失敗，不是推薦修復方法；不可為了 Demo 改成外接 Android。

`sidecar/linux-app/` 的 config／UI 是當時上板的整合版本；主倉庫 App 已更新，
**不要整份直接覆蓋新版**。以 `sources/aco_sidecar_source.py` 作為本機來源，
對照既有 worker／UI 介面逐項整合。正式部署／穩定性驗收仍是後續工作。

## 離線檢查

在 `sidecar/runtime` 執行 `python3 -m unittest test_manual_replay`。
在 `sidecar/linux` 執行 `python3 -m unittest test_aco_sidecar_stream`
（需 NumPy／OpenCV）。這些測試不連探頭、不讀真實 License，不等於上板驗收。
Python 語法檢查也不代表 Android／HAL／Linux UI 所有路徑已驗證。

2026-10-07 重連優化檢查：離線 supervisor／重播安全測試 5 項通過，包含
同 PID、新 `license.sock` 的單次重新佈建；Python 語法編譯通過。Android debug
APK 使用上述 Gradle／SDK／官方 AAR 成功建置、簽章憑證保持不變，並經 SHA-256
差分往返驗證後部署。受控完整 Sidecar 與同 PID Service 重啟均在未開關 P42 的
情況下恢復板內串流。這不等於人體量測斷線或長時間穩定性已通過；細節與界線見
[RECONNECT_OPTIMIZATION_20261007.md](RECONNECT_OPTIMIZATION_20261007.md)。
