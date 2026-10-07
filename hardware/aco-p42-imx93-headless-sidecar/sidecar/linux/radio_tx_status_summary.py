#!/usr/bin/env python3
"""Read only small numeric firmware status counts from recent event logs."""
from collections import Counter
import re
import subprocess

with open('/proc/uptime') as source:
    cutoff = float(source.read().split()[0]) - 90
result = subprocess.run(['dmesg'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
counts = Counter()
for line in result.stdout.splitlines():
    timestamp = re.match(rb'\[\s*(\d+\.\d+)\]', line)
    if not timestamp or float(timestamp.group(1)) < cutoff:
        continue
    found = re.search(rb'Wlan: Tx status: tx_token=\d{1,3}, pkt_type=0x([0-9a-fA-F]{1,8}), status=(\d{1,3})\b', line)
    if found:
        counts[(int(found.group(1), 16), int(found.group(2)))] += 1
for (kind, status), count in sorted(counts.items()):
    print('FW_TX_PACKET_TYPE', kind, 'STATUS', status, 'COUNT', count)
if not counts:
    print('NO_RECENT_FW_TX_STATUS_RECORDS')
