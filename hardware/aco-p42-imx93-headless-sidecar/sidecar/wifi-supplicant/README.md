# Android 12 Wi-Fi supplicant payload

The deployed binary and HIDL libraries are extracted without modification from
Google's official Android 12 (API 31) default ARM64 system image package:

- package: `system-images;android-31;default;arm64-v8a`
- archive: `arm64-v8a-31_r03.zip`
- archive SHA-1: `1052df2d0afc8fe57138db19d5ebd82d10c607da`

The binary uses the standard `nl80211` driver and runs only inside the onboard
Android sidecar.  It does not relay traffic through the development computer.

`aco_wpa_supplicant.conf` is the station-only template. `p2p_disabled=1`
prevents `wlan0` from claiming the single global P2P management role before
Android adds the IW612 driver's dedicated `p2p0` interface.

Binary artifacts are kept under `artifacts/android-wifi-supplicant/` and are
not source code.  Retain the Android image `NOTICE.txt` with redistributed
artifacts.
