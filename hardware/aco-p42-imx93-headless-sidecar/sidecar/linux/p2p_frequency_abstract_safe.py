#!/usr/bin/env python3
"""Read-only on-board supplicant metadata. Never export peer IDs or credentials."""
import collections
import re
import socket
import subprocess
import sys
import uuid

try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
        control.settimeout(3)
        control.bind('\0aco-safe-diag-' + uuid.uuid4().hex)
        control.connect('\0android:wpa_wlan0')
        for command in (b'IFNAME=p2p0 STATUS', b'IFNAME=p2p0 P2P_PEER FIRST'):
            control.send(command)
            data = control.recv(65535)
            for key, value in re.findall(rb'(?m)^(listen_freq|oper_freq|freq|age)=(\d+)\s*$', data):
                print('SUPPLICANT_' + key.decode().upper(), value.decode())
            for value in re.findall(rb'(?m)^wpa_state=([A-Z_]+)\s*$', data):
                if value in (b'DISCONNECTED', b'INACTIVE', b'SCANNING', b'ASSOCIATING', b'ASSOCIATED', b'COMPLETED'):
                    print('SUPPLICANT_STATE', value.decode())
            print('SUPPLICANT_QUERY_FAIL', data.startswith((b'FAIL', b'UNKNOWN')))
except (OSError, TimeoutError):
    print('SUPPLICANT_CONTROL_UNAVAILABLE')

with open('/proc/uptime') as source:
    cutoff = 0 if '--all-boot' in sys.argv else float(source.read().split()[0]) - 90
kernel = subprocess.run(['dmesg'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
counts = collections.Counter()
times = {}
for line in kernel.stdout.splitlines():
    stamp = re.match(rb'\[\s*(\d+\.\d+)\]', line)
    if not stamp or float(stamp[1]) < cutoff:
        continue
    frame = re.search(rb'wlan: (TX|RX) P2P (Provision Discovery Request|Provision Discovery Response|GO Negotiation Request|GO Negotiation Response|GO Negotiation Confirm), channel=(\d+)\b', line)
    if frame:
        key = (frame[1].decode(), frame[2].decode().replace(' ', '_'), int(frame[3]))
        counts[key] += 1
        times.setdefault(key, [float(stamp[1]), float(stamp[1])])[1] = float(stamp[1])
for (direction, kind, channel), count in sorted(counts.items()):
    key = (direction, kind, channel)
    print('RADIO_EVENTS', direction, kind, 'CHANNEL', channel, 'COUNT', count,
          'FIRST_SECONDS', times[key][0], 'LAST_SECONDS', times[key][1])
print('RADIO_MATCHED_EVENTS', sum(counts.values()))
