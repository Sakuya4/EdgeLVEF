#!/usr/bin/env python3
"""Board-only runtime supervisor. Never logs SDK output or credentials."""
import json
import fcntl
import os
import signal
import socket
import stat
import struct
import subprocess
import threading
import time

RUNC = ['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco']
ID = 'aco-android12'
PACKAGE = 'org.edgelvef.acosidecar'
SECRET = '/var/lib/aco-sidecar/secrets/p42.license'
BUNDLE = '/run/media/root-mmcblk0p2/opt/aco-sidecar/android12/bundle/config.json'
stop = threading.Event()


def run(args, timeout=20):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


def android(*args):
    return run(RUNC + ['exec', ID] + list(args))


def state():
    result = run(RUNC + ['state', ID])
    return json.loads(result.stdout) if result.returncode == 0 else None


def deliver():
    # Refuse symlinks, broad permissions, non-root-owned files, or Git ancestors.
    directory = os.path.dirname(SECRET)
    ancestor = directory
    while ancestor != '/':
        if os.path.lexists(os.path.join(ancestor, '.git')):
            raise PermissionError()
        ancestor = os.path.dirname(ancestor)
    info = os.stat(directory, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError()
    descriptor = os.open(SECRET, os.O_RDONLY | os.O_NOFOLLOW)
    payload = bytearray()
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
            raise PermissionError()
        payload.extend(os.read(descriptor, 257))
        if not 1 <= len(payload) <= 256 or any(item in payload for item in (0, 10, 13)):
            raise ValueError()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(3)
            connection.connect('/run/aco-ipc/license.sock')
            connection.sendall(struct.pack('>H', len(payload)))
            connection.sendall(payload)
    finally:
        os.close(descriptor)
        payload[:] = b'\0' * len(payload)


def license_endpoint(pid):
    try:
        info = os.stat('/run/aco-ipc/license.sock', follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISSOCK(info.st_mode):
        return None
    # A Service restart can recreate the private socket without changing the
    # Android process PID. Include the socket identity so that restart receives
    # the License once, while an unchanged endpoint is never reprovisioned.
    return pid, info.st_dev, info.st_ino


def supervise_app(provisioned_endpoint):
    # A diagnostic replay owns this lock only while its process is alive.
    # The kernel releases it even if the replay crashes; no permanent pause.
    with open('/run/aco-ipc/manual-control.lock', 'a') as control:
        try:
            fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return provisioned_endpoint
        pid = android('pidof', PACKAGE).stdout.strip()
        if not pid:
            android('am', 'start-foreground-service', '-n', PACKAGE + '/.AcoSidecarService')
            stop.wait(3)
            pid = android('pidof', PACKAGE).stdout.strip()
        endpoint = license_endpoint(pid) if pid else None
        if endpoint and endpoint != provisioned_endpoint:
            try:
                deliver()
                provisioned_endpoint = endpoint
                print('SIDECAR_LICENSE_IPC_READY: contents withheld', flush=True)
            except (OSError, ValueError):
                print('SIDECAR_LICENSE_WAITING: private file/socket not ready', flush=True)
        return provisioned_endpoint


def main():
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        deadline = time.monotonic() + 120
        while not os.path.isfile(BUNDLE):
            if stop.wait(2) or time.monotonic() > deadline:
                raise RuntimeError('EMMC_MOUNT')
        current = state()
        if current and current['status'] != 'running':
            run(RUNC + ['delete', ID])
            current = None
        if not current:
            result = run(['/bin/sh', '/opt/aco-sidecar/start_android12_sidecar.sh'], timeout=60)
            if result.returncode:
                # Startup errors contain infrastructure labels only, no SDK/secret.
                print(result.stdout.decode('utf-8', errors='replace'), flush=True)
                print(result.stderr.decode('utf-8', errors='replace'), flush=True)
                raise RuntimeError('RUNTIME_START')
        deadline = time.monotonic() + 240
        while android('getprop', 'sys.boot_completed').stdout.strip() != b'1':
            if stop.wait(3) or time.monotonic() > deadline:
                raise RuntimeError('ANDROID_BOOT')
        # No diagnostic ADB TCP listener at product runtime.
        android('setprop', 'service.adb.tcp.port', '-1')
        android('stop', 'adbd')
        # Product runtime keeps only our sanitized state/error-class log tag.
        # Framework/WPS debug messages must not record credential-bearing data.
        android('setprop', 'persist.log.tag', 'S')
        android('setprop', 'persist.log.tag.AcoSidecar', 'I')
        for permission in ('ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION', 'ACCESS_BACKGROUND_LOCATION'):
            android('pm', 'grant', PACKAGE, 'android.permission.' + permission)
        android('cmd', 'location', 'set-location-enabled', 'true')
        android('svc', 'wifi', 'enable')
        print('SIDECAR_ANDROID_READY: on-board only', flush=True)
        provisioned_endpoint = None
        while not stop.is_set():
            current = state()
            if not current or current['status'] != 'running':
                raise RuntimeError('RUNTIME_EXIT')
            provisioned_endpoint = supervise_app(provisioned_endpoint)
            stop.wait(10)
        return 0
    except Exception as error:
        # Fixed layer identifiers only; never arbitrary exception text.
        layer = str(error) if str(error) in ('EMMC_MOUNT', 'RUNTIME_START', 'ANDROID_BOOT', 'RUNTIME_EXIT') else type(error).__name__
        print('SIDECAR_BLOCKED:' + layer, flush=True)
        return 1
    finally:
        current = state()
        if current and current['status'] == 'running':
            # Release the SDK/P2P session before killing Android, so P42 does
            # not retain a stale group across a normal board reboot.
            try:
                android('am', 'stopservice', '-n', PACKAGE + '/.AcoSidecarService')
                for _ in range(5):
                    if not any(name.startswith('p2p-p2p') for name in os.listdir('/sys/class/net')):
                        break
                    time.sleep(1)
            except (OSError, subprocess.TimeoutExpired):
                print('SIDECAR_STOP: Android cleanup unavailable', flush=True)
            run(RUNC + ['kill', ID, 'KILL'])
        run(RUNC + ['delete', ID])


if __name__ == '__main__':
    raise SystemExit(main())
