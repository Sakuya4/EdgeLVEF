SUMMARY = "Select the SPI LCD DRM card for Weston"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://weston-lcd35 file://weston-lcd35.ini file://10-lcd35.conf"
S = "${WORKDIR}"

do_install() {
	install -d ${D}${bindir}
	install -m 0755 ${WORKDIR}/weston-lcd35 ${D}${bindir}/weston-lcd35
	install -d ${D}${sysconfdir}/xdg/weston
	install -m 0644 ${WORKDIR}/weston-lcd35.ini \
		${D}${sysconfdir}/xdg/weston/weston-lcd35.ini
	install -d ${D}${systemd_system_unitdir}/weston.service.d
	install -m 0644 ${WORKDIR}/10-lcd35.conf \
		${D}${systemd_system_unitdir}/weston.service.d/10-lcd35.conf
}

FILES:${PN} += "${sysconfdir}/xdg/weston/weston-lcd35.ini \
                ${systemd_system_unitdir}/weston.service.d/10-lcd35.conf"
RDEPENDS:${PN} += "weston"
