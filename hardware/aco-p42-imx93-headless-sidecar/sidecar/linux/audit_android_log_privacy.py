#!/usr/bin/env python3
"""Private on-board log audit. Never emits credentials or unsanitized SDK logs."""
import re
import subprocess

with open('/var/lib/aco-sidecar/secrets/p42.license', 'rb') as source:
    secret = bytearray(source.read(257))
try:
    command = ['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec', 'aco-android12', 'logcat']
    result = subprocess.run(command + ['-d'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
    if result.returncode:
        raise SystemExit('PRIVACY_AUDIT_UNAVAILABLE')
    safe = re.findall(rb'AcoSidecar: (?:STATE:[A-Z_]+|ACO_[A-Z_]+:[A-Za-z_][A-Za-z_0-9]*)', result.stdout)
    safe += re.findall(rb'AcoSidecar: P2P_PEER_META:matched=(?:false|true go=(?:true|false) keypad=(?:true|false) display=(?:true|false) pbc=(?:true|false))', result.stdout)
    with open('/opt/aco-sidecar/privacy-sanitized-state.log', 'wb') as output:
        output.write(b'\n'.join(line for line in safe if secret not in line) + b'\n')
    if secret in result.stdout:
        # Retain only sanitized evidence, never persist or display the raw buffer.
        subprocess.run(command + ['-c'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=15)
        print('CREDENTIAL_BEARING_LOG_BUFFER_CLEARED; sanitized states preserved')
    else:
        print('NO_LICENSE_BYTES_IN_ANDROID_LOG_BUFFER')
finally:
    secret[:] = b'\0' * len(secret)
