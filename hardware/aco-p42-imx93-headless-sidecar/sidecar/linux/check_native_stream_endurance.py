#!/usr/bin/env python3
"""Read-only continuous native UI frame acceptance using boot monotonic time."""
import json
import re
import subprocess

result = subprocess.run(['journalctl', '-u', 'edgelvef', '-b', '-o', 'json', '--no-pager'],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
if result.returncode:
    raise SystemExit('ENDURANCE_LOG_UNAVAILABLE')
segment = []
last_pid = None
for raw in result.stdout.splitlines():
    entry = json.loads(raw)
    found = re.search(r'UI_RENDERED: (\d+) source=aco_sidecar acquisition_fps=([0-9.]+)',
                      entry.get('MESSAGE', ''))
    if not found:
        continue
    count = int(found.group(1))
    timestamp = int(entry['__MONOTONIC_TIMESTAMP']) / 1_000_000
    pid = entry.get('_PID')
    if segment and (pid != last_pid or count <= segment[-1][1] or timestamp - segment[-1][0] > 25):
        segment = []
    segment.append((timestamp, count, float(found.group(2))))
    last_pid = pid
with open('/proc/uptime') as source:
    now = float(source.read().split()[0])
if not segment:
    raise SystemExit('ENDURANCE_WAITING_FOR_NATIVE_UI_FRAMES')
duration = segment[-1][0] - segment[0][0]
age = now - segment[-1][0]
print('NATIVE_UI_FRAME_COUNT', segment[-1][1])
print('CONTINUOUS_OBSERVED_SECONDS', round(duration, 1))
print('LAST_FRAME_RECORD_AGE_SECONDS', round(age, 1))
print('LATEST_ACQUISITION_FPS', segment[-1][2])
if age > 25:
    print('ENDURANCE_STREAM_INTERRUPTED')
elif duration >= 600:
    print('ENDURANCE_10_MIN_PASS')
else:
    print('ENDURANCE_10_MIN_PENDING')
