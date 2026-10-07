#!/bin/sh
# Board-only startup; service configuration controls persistence.
set -eu
RUNC=/opt/aco-sidecar/bin/runc
STATE=/run/runc-aco
BUNDLE=/run/media/root-mmcblk0p2/opt/aco-sidecar/android12/bundle
DATA=/opt/aco-sidecar/data/android12
ID=aco-android12

fail() { echo "SIDECAR_BLOCKED: $*" >&2; exit 1; }
case "$(uname -r)" in *-aco-sidecar) ;; *) fail 'Sidecar kernel required' ;; esac
test -x "$RUNC" || fail 'runc missing'
test -f "$BUNDLE/config.json" || fail 'eMMC bundle unavailable'
test -d "$DATA/system" || fail 'persistent Android data unavailable'
if test -d "$STATE/$ID"; then
    "$RUNC" --root "$STATE" state "$ID"
    fail 'container already registered; inspect it before changing Wi-Fi ownership'
fi

# Determine the installed package UID without reading any License material.
APP_UID=$(awk '$1 == "org.edgelvef.acosidecar" {print $2}' "$DATA/system/packages.list")
case "$APP_UID" in ''|*[!0-9]*) fail 'installed Sidecar package UID missing' ;; esac

systemctl stop edgelvef-dhcp.service edgelvef-ap.service
# An UP AP netdev retains a moal reference even after hostapd has stopped.
for iface in uap0 mlan0 wfd0 wlan0 wlan1 p2p0; do
    if test -e "/sys/class/net/$iface"; then ip link set "$iface" down; fi
done
if lsmod | awk '$1 == "moal" {found=1} END {exit !found}'; then
    modprobe -r moal || fail 'IW612 still owned by another process; no forced unload'
fi
if lsmod | awk '$1 == "mlan" {found=1} END {exit !found}'; then modprobe -r mlan; fi
modprobe mlan
MLME=${ACO_HOST_MLME:-1}
case "$MLME" in 0|1) ;; *) fail 'invalid host MLME configuration' ;; esac
FW_RELOAD=${ACO_FW_RELOAD:-0}
case "$FW_RELOAD" in 0|1) ;; *) fail 'invalid firmware reload configuration' ;; esac
# Disable both IEEE power saving and firmware auto deep sleep, as in NXP's
# IW612/i.MX93 P2P example. Both parameters were verified with board modinfo.
modprobe moal drv_mode=7 cfg80211_wext=0xf sta_name=wlan uap_name=wlan wfd_name=p2p max_vir_bss=1 host_mlme="$MLME" reg_alpha2=TW ps_mode=2 auto_ds=2 fw_reload="$FW_RELOAD"
for iface in wlan0 wlan1 p2p0; do
    test -e "/sys/class/net/$iface" || fail "IW612 interface missing: $iface"
done
# Deployment is in Taiwan. Without the country setting, fresh boot uses 00
# and some 5 GHz channels are passive-only. Enable the actual TW regulatory
# rules; this alone does not establish why a P42 handshake may time out.
iw reg set TW || fail 'Taiwan regulatory domain setup failed'

mkdir -p /run/binderfs /run/aco-ipc
mountpoint -q /run/binderfs || mount -t binder binder /run/binderfs
for device in binder hwbinder vndbinder; do
    test -c "/run/binderfs/$device" || fail "Binder endpoint missing: $device"
    # Android's standard Binder endpoints must be accessible to its app UIDs.
    chmod 0666 "/run/binderfs/$device"
done
# binder-control remains root-only; IPC and each app socket stay private.
chown "$APP_UID:$APP_UID" /run/aco-ipc
chmod 0770 /run/aco-ipc
cd "$BUNDLE"
"$RUNC" --root "$STATE" run -d "$ID"
"$RUNC" --root "$STATE" state "$ID"
echo 'SIDECAR_STARTED: verify sys.boot_completed and Wi-Fi Direct separately'
