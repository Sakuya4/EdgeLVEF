#!/usr/bin/env python3
"""Board-only bounded telemetry. No images, credentials or raw SDK/radio logs.

5s samples; native UI freshness is limited by its ~10s journal cadence.
Host anchor UTC is approximate (serial dispatch latency), kernel boot times exact.
"""
import argparse
import datetime as dt
import json
import os
import re
import signal
import subprocess
import time

RUNC = ['/opt/aco-sidecar/bin/runc', '--root', '/run/runc-aco', 'exec', 'aco-android12']
stopping = False

def run(args, timeout=4):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return b''

def uptime():
    with open('/proc/uptime') as source:
        return float(source.read().split()[0])

def main():
    global stopping
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--anchor-utc', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 60 <= args.seconds <= 3600:
        raise SystemExit('INVALID_DURATION')
    anchor = dt.datetime.fromisoformat(args.anchor_utc.replace('Z', '+00:00'))
    if anchor.tzinfo is None:
        raise SystemExit('UTC_ANCHOR_REQUIRED')
    if not re.fullmatch(r'/var/log/aco-sidecar/stress-[0-9TZ-]+\.jsonl', args.output):
        raise SystemExit('INVALID_OUTPUT')
    os.makedirs('/var/log/aco-sidecar', mode=0o700, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    started = uptime()
    signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__('stopping', True))
    signal.signal(signal.SIGINT, lambda *_: globals().__setitem__('stopping', True))
    cpu_previous = None
    last_kernel = started
    latest_ui = None
    with os.fdopen(fd, 'w', buffering=1) as output:
        def emit(record):
            now = uptime()
            record['boot_s'] = round(now, 3)
            record['test_s'] = round(now - started, 3)
            record['estimated_utc'] = (anchor + dt.timedelta(seconds=now-started)).isoformat()
            output.write(json.dumps(record, separators=(',', ':')) + '\n')
        emit({'kind': 'start', 'duration_s': args.seconds, 'interval_s': 5,
              'anchor_dispatch_uncertainty_s': 5, 'ui_journal_cadence_s': 10})
        while not stopping and uptime() - started < args.seconds:
            cycle = time.monotonic()
            sample = {'kind': 'sample'}
            with open('/proc/stat') as source:
                cpu = [int(value) for value in source.readline().split()[1:9]]
            if cpu_previous:
                delta = [a-b for a,b in zip(cpu,cpu_previous)]
                sample['cpu_busy_pct'] = round(100 * (sum(delta)-delta[3]-delta[4]) / max(1,sum(delta)), 1)
            cpu_previous = cpu
            with open('/proc/meminfo') as source:
                memory = source.read()
            for key in ('MemAvailable', 'SwapFree'):
                found = re.search(r'^'+key+r':\s+(\d+) kB', memory, re.M)
                if found:
                    sample[key+'_kb'] = int(found[1])
            pid = run(RUNC + ['pidof', 'org.edgelvef.acosidecar']).strip()
            sample['android_pid'] = int(pid) if pid.isdigit() else None
            data = run(RUNC + ['dumpsys', 'wifip2p'])
            state = re.search(rb'^curState=([A-Za-z]+State)\s*$', data, re.M)
            if state:
                sample['p2p_state'] = state[1].decode()
            formed = re.search(rb'^mWifiP2pInfo groupFormed: (true|false)', data, re.M)
            sample['group'] = formed[1] == b'true' if formed else None
            journal = run(['journalctl', '-u', 'edgelvef', '-b', '-n', '40', '-o', 'json', '--no-pager'])
            for line in journal.splitlines():
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                frame = re.search(r'UI_RENDERED: (\d+) source=aco_sidecar acquisition_fps=([0-9.]+)', entry.get('MESSAGE',''))
                if frame:
                    latest_ui = (int(entry['__MONOTONIC_TIMESTAMP'])/1e6, int(frame[1]), float(frame[2]))
            if latest_ui:
                sample.update(ui_count=latest_ui[1], ui_fps=latest_ui[2],
                              ui_record_age_s=round(uptime()-latest_ui[0],2),
                              ui_record_boot_s=latest_ui[0])
            for name in os.listdir('/sys/class/net'):
                if not re.fullmatch(r'p2p-p2p[0-9]+-[0-9]+', name):
                    continue
                telemetry = {}
                for key in ('rx_bytes','tx_bytes','rx_packets','tx_packets','rx_errors','tx_errors','rx_dropped','tx_dropped'):
                    try:
                        with open('/sys/class/net/'+name+'/statistics/'+key) as source:
                            telemetry[key] = int(source.read())
                    except OSError:
                        # A group can disappear during this read-only sample.
                        continue
                station = run(['iw', 'dev', name, 'station', 'dump'])
                for key, pattern in {
                    'signal_dbm': rb'\bsignal:\s*(-?\d+)',
                    'signal_avg_dbm': rb'\bsignal avg:\s*(-?\d+)',
                    'tx_retries': rb'\btx retries:\s*(\d+)',
                    'tx_failed': rb'\btx failed:\s*(\d+)',
                    'tx_bitrate_mbps': rb'\btx bitrate:\s*([0-9.]+)',
                    'rx_bitrate_mbps': rb'\brx bitrate:\s*([0-9.]+)',
                }.items():
                    match = re.search(pattern, station)
                    if match:
                        telemetry[key] = float(match[1])
                info = run(['iw','dev',name,'info'])
                freq = re.search(rb'\bchannel (\d+) \((\d+) MHz\)', info)
                if freq:
                    telemetry.update(channel=int(freq[1]), frequency_mhz=int(freq[2]))
                sample['radio'] = telemetry
            sample['sampling_work_ms'] = round((time.monotonic()-cycle)*1000,1)
            emit(sample)
            for line in run(['dmesg']).splitlines():
                stamp = re.match(rb'\[\s*(\d+\.\d+)\]', line)
                if not stamp or float(stamp[1]) <= last_kernel:
                    continue
                timestamp = float(stamp[1])
                last_kernel = max(last_kernel, timestamp)
                if re.search(rb'(Disconnected|disassoc)', line, re.I):
                    reason = re.search(rb'reason(?:\s+code)?\s*[:=]?\s*(\d+)',line,re.I)
                    if reason:
                        emit({'kind':'radio_disconnect','event_boot_s':timestamp,'reason':int(reason[1])})
                frame = re.search(rb'wlan: (TX|RX) P2P (Provision Discovery Request|Provision Discovery Response), channel=(\d+)\b',line)
                if frame:
                    emit({'kind':'p2p_action','event_boot_s':timestamp,'direction':frame[1].decode(),
                          'action':frame[2].decode().replace(' ','_'),'channel':int(frame[3])})
            while not stopping and time.monotonic()-cycle < 5:
                time.sleep(0.2)
        emit({'kind':'end','cancelled':stopping})
        os.fsync(output.fileno())
    print('STRESS_CAPTURE_COMPLETE: sanitized board-local telemetry', flush=True)

if __name__ == '__main__':
    main()
