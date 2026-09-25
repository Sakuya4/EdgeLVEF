# FRDM-i.MX93 的 3.5 吋 RPi SPI 螢幕支援

本資料夾提供已在 FRDM-i.MX93 11x11 實機驗證的驅動方式，適用於背面標示
「3.5inch RPi Display、480x320 pixel、XPT2046 touch controller」的螢幕。
測試核心為 NXP LF6.6.36_2.1.0 的
`6.6.36-lts-next-gab2a7006a738`。

支援內容包括：

- ILI9486 相容 LCD 的 DRM／framebuffer 驅動；
- XPT2046 的 ADS7846 觸控驅動；
- 獨立且可回復的 `imx93-11x11-frdm-lcd35.dtb`；
- 自動選取 SPI DRM 裝置與 Pixman renderer 的 Weston 設定；
- 可在無網路時經 COM3 使用的 Windows PowerShell 工具。

## 重要限制

- COM3 是 Cortex-A55 的 Linux／U-Boot console；COM4 是 Cortex-M33，本方案
  不使用 COM4。
- P11 pin 22（GPIO_IO25）原本與 CAN2 共用，因此 LCD 專用 DTB 會停用
  CAN2，將此腳改作 LCD reset。
- LPSPI3 進行全畫面 RGB565 傳輸時，DMA 會發生 timeout；本方案在裝置樹
  移除 DMA 屬性，強制採用已實測成功的 PIO。
- GPIO 訊號為 3.3 V，請勿把 5 V 邏輯接到 i.MX93 訊號腳。

## P11 接線

| P11 實體腳位 | i.MX93 訊號 | LCD／觸控功能 |
|---:|---|---|
| 11 | GPIO_IO17 / GPIO2_IO17 | XPT2046 IRQ |
| 18 | GPIO_IO24 / GPIO2_IO24 | LCD D/C (RS) |
| 19 | GPIO_IO10 / LPSPI3_SOUT | MOSI |
| 21 | GPIO_IO09 / LPSPI3_SIN | MISO |
| 22 | GPIO_IO25 / GPIO2_IO25 | LCD reset |
| 23 | GPIO_IO11 / LPSPI3_SCK | SCLK |
| 24 | GPIO_IO08 / GPIO2_IO08 | LCD CS0 |
| 26 | GPIO_IO07 / GPIO2_IO07 | XPT2046 CS1 |

電源與 GND 請依螢幕板標示連接。

## Yocto 建置

在已初始化的 NXP Scarthgap Yocto 環境加入 layer：

```sh
bitbake-layers add-layer /path/to/EdgeLVEF/hardware/imx93-rpi-lcd35/meta-imx93-lcd35
```

在 `conf/local.conf` 加入：

```conf
IMAGE_INSTALL:append = " lcd35-weston"
```

接著建置原本供 FRDM-i.MX93 使用的 image。此 layer 會加入 LCD DTB、
`CONFIG_TINYDRM_ILI9486=y`、`CONFIG_TOUCHSCREEN_ADS7846=y` 及 Weston
設定。請將新核心部署為 `Image.lcd35`，並部署
`imx93-11x11-frdm-lcd35.dtb` 與更新後的 rootfs；不要刪除原始
`Image` 和 `imx93-11x11-frdm.dtb`。

在 U-Boot 選用新核心與 DTB：

```text
setenv image Image.lcd35
setenv fdtfile imx93-11x11-frdm-lcd35.dtb
saveenv
boot
```

也可由 Windows 經 COM3 操作。第一次先不要保存環境；成功後再加上
`-SaveEnvironment`：

```powershell
.\tools\uboot_lcd35_boot.ps1 -PortName COM3
.\tools\uboot_lcd35_boot.ps1 -PortName COM3 -SaveEnvironment
```

## 開機後確認

```sh
cat /proc/device-tree/model
dmesg | grep -Ei 'ili9486|ads7846|spi|drm'
ls -l /dev/dri /dev/fb* /dev/input/event*
for f in /sys/class/drm/card*-*/status; do echo "$f: $(cat "$f")"; done
systemctl status weston --no-pager
```

本次實測結果為 `/dev/dri/card1`、`/dev/fb0`（`ili9486drmfb`）以及
XPT2046 的 `/dev/input/event1`；若另外啟用其他裝置，編號可能改變。

螢幕只有白色背光代表已通電，但尚未收到正確初始化或畫面資料，不能用來
判定驅動已成功，應以上述指令確認。

### 480×320 的介面大小

此面板只有 480×320 原生模式，ILI9486 DRM 不支援任意虛擬解析度。本方案
因此固定 Weston 使用 `480x320`、`scale=1`，並將 Qt／GTK client 縮放為
75%；terminal 會以 9 pixel 字體最大化開啟。

若自製應用程式仍過大，可在 `10-lcd35.conf` 同步調整
`QT_SCALE_FACTOR` 與 `GDK_DPI_SCALE`。建議範圍為 `0.65`～`1.0`，數值
越小，按鈕與文字越小。修改後執行：

```sh
systemctl daemon-reload
systemctl restart weston
```

應用程式本身仍應採用能適應約 640×426 邏輯工作區的版面；固定為
800×480 或一般桌機大小的視窗，無法只靠 LCD 驅動完整顯示。

## 回復原始開機設定

若新 DTB 無法啟動，從 COM3 中斷 U-Boot，執行：

```text
setenv image Image
setenv fdtfile imx93-11x11-frdm.dtb
saveenv
boot
```

英文版 [README.md](README.md) 另有診斷工具與完整驗證說明。
