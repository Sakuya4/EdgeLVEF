# FRDM-i.MX93 3.5-inch RPi SPI display support

This directory contains the tested board support for a Raspberry Pi-style
3.5-inch, 480 x 320 SPI display using an ILI9486-compatible LCD controller and
an XPT2046 touch controller.

The support was validated on an NXP FRDM-i.MX93 11x11 board with NXP Linux
`6.6.36-lts-next-gab2a7006a738` from the LF6.6.36_2.1.0 release. It provides:

- an additional, rollback-safe device tree named
  `imx93-11x11-frdm-lcd35.dtb`;
- the upstream `ili9486` DRM/fbdev driver;
- the upstream `ads7846` input driver for XPT2046;
- a Weston launcher which selects the SPI DRM card and Pixman renderer; and
- COM3 diagnostic, upload, and U-Boot helpers for a Windows host.

For Traditional Chinese instructions, see [README.zh-TW.md](README.zh-TW.md).

## Important hardware constraints

- The display is connected directly to the 3.3 V P11 GPIO/SPI header. Do not
  put 5 V logic on an i.MX93 signal pin.
- COM3 is the Cortex-A55 Linux/U-Boot console. COM4 is the Cortex-M33 console
  and is not used by these tools.
- GPIO_IO25 is shared with CAN2 on the base board. The LCD-specific device tree
  disables CAN2 so that this pin can be the display reset line.
- LPSPI3 DMA must be disabled for this panel. Full-frame RGB565 transfers timed
  out with `I/O Error in DMA TX`; the supplied device tree removes the DMA
  properties and uses PIO.

## P11 wiring

| P11 pin | i.MX93 signal | Display signal |
|---:|---|---|
| 11 | GPIO_IO17 / GPIO2_IO17 | XPT2046 IRQ |
| 18 | GPIO_IO24 / GPIO2_IO24 | LCD D/C (RS) |
| 19 | GPIO_IO10 / LPSPI3_SOUT | MOSI |
| 21 | GPIO_IO09 / LPSPI3_SIN | MISO |
| 22 | GPIO_IO25 / GPIO2_IO25 | LCD reset |
| 23 | GPIO_IO11 / LPSPI3_SCK | SCLK |
| 24 | GPIO_IO08 / GPIO2_IO08 | LCD CS0 |
| 26 | GPIO_IO07 / GPIO2_IO07 | XPT2046 CS1 |

Also connect the display's 3.3 V and ground pins according to the display
board markings.

## Directory contents

```text
meta-imx93-lcd35/  Yocto layer: kernel patch, DTB, and Weston integration
tools/              COM3 deployment and low-level diagnostic tools
```

The kernel patch intentionally adds a new DTB rather than replacing the stock
one. This keeps the original board boot path available for recovery.

## Yocto integration

Use the NXP LF6.6.36_2.1.0 Scarthgap BSP, or review and refresh the kernel patch
before applying it to a different BSP release.

From an initialized Yocto build environment, add this layer:

```sh
bitbake-layers add-layer /path/to/EdgeLVEF/hardware/imx93-rpi-lcd35/meta-imx93-lcd35
```

Add the Weston integration package to `conf/local.conf`:

```conf
IMAGE_INSTALL:append = " lcd35-weston"
```

Build the same image target used for the board. The layer appends the following
kernel features automatically:

- `CONFIG_TINYDRM_ILI9486=y`
- `CONFIG_TOUCHSCREEN_ADS7846=y`
- `freescale/imx93-11x11-frdm-lcd35.dtb`

Deploy the resulting kernel as `Image.lcd35`, deploy
`imx93-11x11-frdm-lcd35.dtb`, and deploy the rebuilt root filesystem. Keep the
stock `Image` and `imx93-11x11-frdm.dtb` on the boot medium.

Select the LCD build in U-Boot:

```text
setenv image Image.lcd35
setenv fdtfile imx93-11x11-frdm-lcd35.dtb
saveenv
boot
```

The Windows helper can perform the same selection through COM3. Omit
`-SaveEnvironment` for a one-boot test; add it only after the test succeeds:

```powershell
.\tools\uboot_lcd35_boot.ps1 -PortName COM3
.\tools\uboot_lcd35_boot.ps1 -PortName COM3 -SaveEnvironment
```

## Runtime verification

After Linux starts, verify the LCD DRM device, framebuffer, touch input, and
Weston service:

```sh
cat /proc/device-tree/model
dmesg | grep -Ei 'ili9486|ads7846|spi|drm'
ls -l /dev/dri /dev/fb* /dev/input/event*
for f in /sys/class/drm/card*-*/status; do echo "$f: $(cat "$f")"; done
systemctl status weston --no-pager
```

The tested system registers the LCD as `/dev/dri/card1`, the compatibility
framebuffer as `/dev/fb0` (`ili9486drmfb`), and XPT2046 as
`/dev/input/event1`. Card and event numbers are discovery-based and may change
if other devices are enabled.

### UI sizing on the 480 x 320 panel

This panel has only one native mode and the ILI9486 DRM driver cannot expose a
larger virtual mode. The supplied configuration therefore keeps Weston at
`480x320`, explicitly uses compositor scale 1, and scales Qt/GTK clients to
75%. The terminal launcher uses a 9-pixel font and opens maximized.

If a custom application is still too large, adjust `QT_SCALE_FACTOR` and
`GDK_DPI_SCALE` together in `10-lcd35.conf`. Values from `0.65` to `1.0` are
reasonable; lower values make application controls and text smaller. Rebuild
the package or edit the installed systemd drop-in, then run:

```sh
systemctl daemon-reload
systemctl restart weston
```

Application layouts should still be responsive at a logical viewport near
640 x 426. A fixed 800 x 480 or desktop-sized window cannot be made fully
visible solely by changing the LCD driver.

From Windows, a command can also be run over COM3:

```powershell
.\tools\serial_exec.ps1 -PortName COM3 -Command "cat /proc/device-tree/model"
```

## Low-level diagnostics

`lcd35_spi_test.c` draws RGB565 color bars without changing U-Boot. Run it only
while using a device tree that exposes the LCD chip select as `spidev`; after
the DRM driver binds that SPI device, `spidev` is intentionally unavailable.

```powershell
.\tools\deploy_lcd35_test.ps1 -PortName COM3
```

`xpt2046_test.c` reads raw touch samples for wiring diagnostics. The
`serial_upload.ps1` and `serial_exec.ps1` helpers can transfer and execute
other small test files without a network connection.

## Rollback

Interrupt U-Boot on COM3 and restore the original selections:

```text
setenv image Image
setenv fdtfile imx93-11x11-frdm.dtb
saveenv
boot
```

A white backlight alone means that the panel is powered but has not received a
valid initialization/frame update. It is not proof that the DRM driver is
running; use the runtime checks above.
