#!/usr/bin/env python3
"""Bounded NXP event-status observation; no packet bytes or credential output.

The pinned driver's MEVENT bit is 1<<5; its event logs have no MEVENT hexdump.
Do not enable MDAT_D/MCMD_D or general supplicant/SDK debug output.
"""
import re
from collections import Counter
import signal
import subprocess
import time

DEBUG = '/proc/mwlan/adapter0/p2p0/debug'


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError()))
    with open(DEBUG) as source:
        found = re.search(r'^drvdbg=(\d+)$', source.read(), re.M)
    if not found:
        raise ValueError()
    previous = int(found.group(1))
    with open('/proc/uptime') as source:
        started = float(source.read().split()[0])
    try:
        with open(DEBUG, 'w') as control:
            control.write('drvdbg=' + str(previous | (1 << 5)) + '\n')
        print('RADIO_ACK_OBSERVING: 40 seconds, event-status only', flush=True)
        time.sleep(40)
    finally:
        with open(DEBUG, 'w') as control:
            control.write('drvdbg=' + str(previous) + '\n')
        print('RADIO_DEBUG_RESTORED', flush=True)
    result = subprocess.run(['dmesg'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=10)
    statuses = []
    tx = rx = 0
    channels = Counter()
    for line in result.stdout.splitlines():
        timestamp = re.match(rb'\[\s*(\d+\.\d+)\]', line)
        if not timestamp or float(timestamp.group(1)) < started:
            continue
        status = re.search(rb'Wlan: Tx status=([01])\b', line)
        if status:
            statuses.append(int(status.group(1)))
        tx += bool(re.search(rb'wlan: TX P2P Provision Discovery Request, channel=161\b', line))
        rx += bool(re.search(rb'wlan: RX P2P Provision Discovery Response, channel=161\b', line))
        frame = re.search(rb'wlan: (TX|RX) P2P (Provision Discovery Request|Provision Discovery Response), channel=(\d+)\b', line)
        if frame:
            channels[(frame[1].decode(), frame[2].decode().replace(' ', '_'), int(frame[3]))] += 1
    print('TX_STATUS_ACK_TRUE', statuses.count(1))
    print('TX_STATUS_ACK_FALSE', statuses.count(0))
    print('TX_PROVISION_REQUEST_CH161', tx)
    print('RX_PROVISION_RESPONSE_CH161', rx)
    # Preserve old channel-specific fields, but never mistake their zeros for
    # absence of handshake on a different operating channel.
    for (direction, kind, channel), count in sorted(channels.items()):
        print('P2P_CHANNEL_EVENT', direction, kind, channel, count)
    print('P2P_ALL_CHANNEL_EVENTS', sum(channels.values()))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('RADIO_ACK_OBSERVATION_FAILED:' + type(error).__name__)
        raise SystemExit(1)
