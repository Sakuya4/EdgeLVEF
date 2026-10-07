#!/usr/bin/env python3
"""Read public P2P capability bits, never identifiers, PINs or credentials."""
import re
import subprocess

result = subprocess.run(['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec',
                         'aco-android12', 'dumpsys', 'wifip2p'], capture_output=True, timeout=15)
count = 0
for label, value in re.findall(rb'(?i)(group\s*capab|grp\s*capab|grpcapab|groupCapability|dev\s*capab|devcapab|wpsConfigMethodsSupported|wps)\s*[:=]\s*(0x[0-9a-f]{1,4}|[0-9]{1,5})\b', result.stdout):
    print(label.decode(), value.decode())
    count += 1
print('CAPABILITY_FIELDS', count)
