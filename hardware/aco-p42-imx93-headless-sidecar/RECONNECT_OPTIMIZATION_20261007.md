# P42 reconnect optimization — 2026-10-07

Architecture remains P42 → on-board headless Android Sidecar → board-local IPC
→ native Linux EdgeLVEF. No external Android device, host relay, cloud path, or
License bypass was introduced.

## Changes

- Bound every Aco connection attempt, including an SDK-reported
  `isConnecting()` state, to 20 seconds. A previously successful physical
  connection took approximately 17.2 seconds, so a 15-second draft limit was
  rejected before final acceptance.
- Replace the previous fixed 30-second connection throttle with a 2-second
  recovery backoff.
- Preserve a 5-second grace period after `probe.connect()`, because the official
  AAR initially continues to report `isDisconnected()` while its asynchronous
  Wi-Fi Direct transition begins.
- Before accepting a fresh probe after a failed or lost session, call the
  official `stop()`/`disconnect()` lifecycle, clear local frames, and restart
  discovery after the short backoff.
- Identify private License provisioning by Android PID plus the board-local
  `license.sock` device/inode. A Service restart can recreate that socket while
  retaining the same process PID; the previous PID-only supervisor incorrectly
  withheld License in that case.

## Preserved failed experiment

The first APK revision treated the SDK's immediate post-`connect()`
`isDisconnected()` state as a terminal failure. At board time 17:40:55 it
logged `CONNECTING` followed approximately 20 ms later by `CONNECT_FAILED`, and
PID 2905 exited with Android reason 4 (app crash). This APK is not the accepted
revision. It remains on the board only as the recoverable backup
`/opt/aco-sidecar/apks/aco-sidecar-reconnect-fast-v1.apk`.

The correction reinstated a 5-second disconnected-state grace period while
retaining the absolute 20-second connecting timeout. Offline supervisor tests
were expanded from three to five and all passed, including same-PID/new-socket
reprovisioning and unchanged-socket non-reprovisioning.

## Deployed revision and verification

- Installed APK SHA-256:
  `cba3975cd1bda6b3a6e76fc8c139b804a1744c7dcbf16d49921738f33886d86d`
- APK signing certificate SHA-256 remains:
  `ef305db2f80fc9f99aa45856af6e91165423745dbb50a7afddd1faed42eb855e`
- Deployed supervisor SHA-256:
  `927dcfc19955403e7264b81b7e787f182b5a5f1c9d7c6adfe93161b6b42cbcb6`
- Previous installed APK backup:
  `/opt/aco-sidecar/apks/aco-sidecar-c986-backup.apk`
- Previous supervisor backup:
  `/opt/aco-sidecar/sidecar_supervisor.py.before-socket-token`

Every uploaded delta/script and every reconstructed APK was checked by SHA-256
before use. `pm install -r` returned `Success`; existing package data and
permissions were preserved. The legal License remained only in the existing
root-owned private board file and board-local Unix socket, and was never printed,
copied into an APK, or written into this evidence.

## Board tests

### Full on-board Android Sidecar restart, P42 left powered

- New app `STARTED`: 17:45:44.964
- Private License received: 17:45:45.840
- P42 selected / `CONNECTING`: 17:45:49.536
- `STREAMING`: 17:46:01.594
- Linux UI reported `SIDECAR_FRAME_LIVE`: 17:46:05

The P42 was not power-cycled. Android reached `GroupCreatedState`, the P42 was
group owner at `10.0.110.2`, and native acquisition returned to approximately
6–7 FPS. App start to SDK streaming was approximately 16.6 seconds; the actual
connect phase was approximately 12.1 seconds.

### Same Android PID, Service-only restart

- Android PID before and after: 1433
- Service `STARTED`: 17:46:23.810
- New `license.sock` received License: 17:46:26.373
- P42 selected / `CONNECTING`: 17:46:34.472
- `STREAMING`: 17:46:36.989
- Linux UI reported `SIDECAR_FRAME_LIVE`: 17:46:40

This proves the new socket-identity supervisor logic fixes the previous
same-PID License starvation. Service start to SDK streaming was approximately
13.2 seconds and the final connection phase approximately 2.5 seconds. No new
app crash was recorded.

### Final 20-second-timeout APK installation

The accepted APK was installed over the tested 15-second draft while the P42
remained powered:

- App `STARTED`: 17:49:10.395
- Private License received: 17:49:11.775
- P42 selected / `CONNECTING`: 17:49:14.420
- `STREAMING`: 17:49:24.458
- Linux UI reported `SIDECAR_FRAME_LIVE`: 17:49:26

The final connect phase took approximately 10.0 seconds and app start to SDK
streaming approximately 14.1 seconds. Android reported `GroupCreatedState` with
the P42 as group owner. The prior 15-second draft remains only as a rollback
artifact; the installed revision uses the accepted 20-second upper bound.

## Scope still requiring physical verification

These controlled recovery tests improve the previously observed approximately
55-second reconnect and remove the need for a P42 power cycle in the two tested
restart paths. They do not yet prove recovery from the body-measurement-specific
radio loss, nor ten-/thirty-minute endurance during real ultrasound use. The
next test must preserve P42 lamp state and correlate actual body contact with
RSSI/TX failures, P2P group loss, SDK state, Android PID, and native frame age.
