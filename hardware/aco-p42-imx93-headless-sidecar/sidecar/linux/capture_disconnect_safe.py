#!/usr/bin/env python3
"""Emit only fixed diagnostic fields, never raw wireless or SDK messages."""
import re
import subprocess

kernel = subprocess.run(['dmesg'], stdout=subprocess.PIPE, check=True, timeout=15)
for line in kernel.stdout.splitlines():
    if not re.search(rb'(?:Disconnected|disassoc)', line, re.I):
        continue
    stamp = re.match(rb'\[\s*([0-9.]+)\]', line)
    reason = re.search(rb'reason(?:\s+code)?\s*[:=]?\s*(\d+)', line, re.I)
    if stamp and reason:
        print('KERNEL_DISCONNECT_SECONDS', stamp[1].decode(), 'REASON', reason[1].decode())
for unit in ('aco-sidecar', 'edgelvef', 'edgelvef-ap', 'edgelvef-dhcp'):
    active = subprocess.run(['systemctl', 'is-active', unit], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=10)
    state = active.stdout.strip()
    if state in (b'active', b'inactive', b'failed', b'unknown'):
        print('UNIT', unit, state.decode())
