#!/usr/bin/env python3
"""Replay discovery-before-License entirely on board, with bounded supervision."""
import argparse
import fcntl
import re
import signal
import subprocess
import time

from sidecar_supervisor import android, deliver, PACKAGE

ALLOWED = {'DISCOVERING', 'STARTED', 'LICENSE_RECEIVED', 'PROBE_SELECTED',
           'CONNECTING', 'STREAMING', 'DISCONNECTED', 'RETRY_DISCOVERY',
           'MULTIPLE_PROBES_REFUSED', 'INITIALIZE_FAILED', 'PERMISSIONS_REQUIRED',
           'WIFI_P2P_UNAVAILABLE'}


def states(pid):
    result = android('logcat', '-d', '--pid=' + pid, '-s', 'AcoSidecar:I')
    # Never emit the raw buffer, exceptions, identifiers, or License contents.
    return [value.decode() for value in re.findall(rb'AcoSidecar: STATE:([A-Z_]+)', result.stdout)
            if value.decode() in ALLOWED]


def ui_marker():
    result = subprocess.run(['journalctl', '-u', 'edgelvef', '-n', '60', '--no-pager', '-o', 'cat'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    records = re.findall(rb'UI_RENDERED[^\r\n]*', result.stdout)
    return records[-1] if records else b''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--license-first', action='store_true')
    args = parser.parse_args()
    if not 30 <= args.timeout <= 180:
        raise ValueError()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError()))
    with open('/run/aco-ipc/manual-control.lock', 'a') as control:
        fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if android('getprop', 'sys.boot_completed').stdout.strip() != b'1':
            raise RuntimeError('ANDROID_NOT_READY')
        # Normal service cleanup releases SDK state before a clean app process.
        android('am', 'stopservice', '-n', PACKAGE + '/.AcoSidecarService')
        time.sleep(2)
        android('am', 'force-stop', PACKAGE)
        android('am', 'start-foreground-service', '-n', PACKAGE + '/.AcoSidecarService')
        print('REPLAY_APP_STARTED', flush=True)
        started = time.monotonic()
        pid = None
        delivered = False
        printed = 0
        baseline = ui_marker()
        while time.monotonic() - started < args.timeout:
            current = android('pidof', PACKAGE).stdout.strip().decode('ascii')
            if not current:
                time.sleep(1)
                continue
            if not current.isdigit():
                raise RuntimeError('MULTIPLE_APP_PROCESSES')
            if pid and pid != current:
                raise RuntimeError('APP_RESTARTED')
            pid = current
            observed = states(pid)
            for state in observed[printed:]:
                print('REPLAY_STATE:' + state, flush=True)
            printed = len(observed)
            if not delivered and (args.license_first or 'PROBE_SELECTED' in observed):
                try:
                    deliver()
                    delivered = True
                    print('REPLAY_LICENSE_IPC_SENT: contents withheld', flush=True)
                except OSError:
                    pass
            if 'STREAMING' in observed and ui_marker() != baseline and ui_marker():
                print('REPLAY_VERIFIED: SDK streaming and new native Linux UI_RENDERED record', flush=True)
                return 0
            time.sleep(2)
        print('REPLAY_BLOCKED:' + ('P2P_HANDSHAKE' if delivered else 'PROBE_DISCOVERY'), flush=True)
        snapshot = android('dumpsys', 'wifip2p').stdout
        state = re.search(rb'^curState=([A-Za-z]+State)\s*$', snapshot, re.M)
        if state:
            print('REPLAY_P2P_STATE:' + state.group(1).decode(), flush=True)
        return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('REPLAY_FAILED:' + type(error).__name__, flush=True)
        raise SystemExit(1)
