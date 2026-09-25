FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append = " file://0001-arm64-dts-imx93-frdm-add-lcd35.patch"

KERNEL_DEVICETREE:append:imx93frdm = " freescale/imx93-11x11-frdm-lcd35.dtb"
