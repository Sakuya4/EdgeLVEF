#!/usr/bin/env python3
"""Read-only supplicant peer frequency metadata; no identifiers or WPS data."""
import json
import re
import subprocess

state = subprocess.run(['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco',
                        'state', 'aco-android12'], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, timeout=10)
pid = int(json.loads(state.stdout)['pid'])
socket = '/proc/' + str(pid) + '/root/dev/socket/wpa_wlan0'
try:
    result = subprocess.run(['wpa_cli', '-g', socket, 'raw',
                             'IFNAME=p2p0', 'P2P_PEER', 'FIRST'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
except subprocess.TimeoutExpired:
    print('PEER_CONTROL_TIMEOUT')
    raise SystemExit(2)
if result.returncode:
    print('PEER_CONTROL_UNAVAILABLE')
else:
    fields = re.findall(rb'(?m)^(listen_freq|oper_freq|level|age)=(\d+)\s*$', result.stdout)
    for key, value in fields:
        print('PEER_' + key.decode().upper(), value.decode())
    print('PEER_FREQUENCY_FIELDS', len(fields))
    print('PEER_CONTROL_FAIL', bool(re.search(rb'(?m)^FAIL', result.stdout)))
