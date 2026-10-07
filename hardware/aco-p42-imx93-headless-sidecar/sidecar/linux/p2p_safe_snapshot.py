#!/usr/bin/env python3
"""Emit only allowlisted P2P states/counts, never peer IDs or WPS credentials."""
import re
import subprocess

result = subprocess.run(
    ['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec',
     'aco-android12', 'dumpsys', 'wifip2p'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20,
)
if result.returncode:
    raise SystemExit('P2P_SNAPSHOT_UNAVAILABLE')
data = result.stdout
for pattern in (
    rb'^curState=([A-Za-z]+State)\s*$',
    rb'^mDiscoveryStarted (true|false)\s*$',
    rb'^mWifiP2pInfo groupFormed: (true|false)',
):
    found = re.search(pattern, data, re.M)
    if found:
        print(pattern.split(b'=')[0].split(b' ')[0].lstrip(b'^').decode(),
              found.group(1).decode())
print('PEER_DEVICE_RECORDS', len(re.findall(rb'^\s*Device: ', data, re.M)))
for event in (b'P2P-PROV-DISC-FAILURE', b'P2P-PROV-DISC-ENTER-PIN',
              b'P2P-GROUP-STARTED', b'P2P-GROUP-REMOVED'):
    print(event.decode(), data.count(event))
# Android's StateMachine history uses symbolic event names, not supplicant
# wire strings. Only fixed enum-like names are emitted, never message payloads.
for event in sorted(set(re.findall(rb'\b(?:P2P|CMD|SUP)_[A-Z_]{3,64}\b', data))):
    if any(token in event for token in (b'PROV', b'GROUP', b'CONNECT', b'FIND')):
        print('HISTORY_EVENT', event.decode(), data.count(event))
