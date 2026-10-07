#!/usr/bin/env python3
"""Read Android process exit reason numbers only, no crash text/credentials."""
import re
import subprocess

result = subprocess.run(['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec',
                         'aco-android12', 'dumpsys', 'activity', 'exit-info',
                         'org.edgelvef.acosidecar'], stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, timeout=20)
count = 0
for line in result.stdout.splitlines():
    for stamp in re.findall(rb'\btimestamp=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)', line):
        print('EXIT_TIMESTAMP', stamp.decode())
    for label, value in re.findall(rb'\b(reason|status|importance|pss|rss|pid)=(\d+)\b', line):
        print(label.decode(), value.decode())
        count += 1
print('EXIT_REASON_FIELDS', count)
crash = subprocess.run(['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec',
                        'aco-android12', 'logcat', '-b', 'crash', '-d'],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
# Exception class and conventional stack-frame syntax only; no exception
# messages (which might contain SDK arguments), thread names or raw log lines.
classes = sorted(set(re.findall(rb'\b(?:java|android|org\.edgelvef|com\.aco)[A-Za-z0-9_.$]*(?:Exception|Error)\b', crash.stdout)))
for name in classes:
    print('CRASH_CLASS', name.decode())
for frame in re.findall(rb'\bat ([A-Za-z0-9_.$]+)\(([A-Za-z0-9_.]+:(?:\d+)|Native Method|Unknown Source)\)', crash.stdout)[-20:]:
    print('CRASH_FRAME', frame[0].decode(), frame[1].decode())
print('CRASH_SAFE_CLASSES', len(classes))
dropbox = subprocess.run(['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec',
                          'aco-android12', 'dumpsys', 'dropbox', '--print', 'data_app_crash'],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
# Keep each entry private. Only our process's conventional Java stack syntax
# is exportable; raw description, exception messages and extras are excluded.
entries = re.split(rb'(?m)^={5,}\s*$', dropbox.stdout)
matched = 0
for entry in entries:
    if not re.search(rb'(?m)^Process: org\.edgelvef\.acosidecar\s*$', entry):
        continue
    matched += 1
    for stamp in re.findall(rb'(?m)^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) data_app_crash', entry):
        print('DROPBOX_TIMESTAMP', stamp.decode())
    for pid in re.findall(rb'(?m)^PID: (\d+)\s*$', entry):
        print('DROPBOX_PID', pid.decode())
    for name in sorted(set(re.findall(rb'\b(?:java|android|org\.edgelvef|com\.aco)[A-Za-z0-9_.$]*(?:Exception|Error)\b', entry))):
        print('DROPBOX_CLASS', name.decode())
    for frame in re.findall(rb'\bat ([A-Za-z0-9_.$]+)\(([A-Za-z0-9_.]+:(?:\d+)|Native Method|Unknown Source)\)', entry)[:80]:
        print('DROPBOX_FRAME', frame[0].decode(), frame[1].decode())
    for errno in sorted(set(re.findall(rb'\b(ECONNREFUSED|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|ECONNRESET)\b', entry))):
        print('DROPBOX_ERRNO', errno.decode())
print('DROPBOX_MATCHED_ENTRIES', matched)
