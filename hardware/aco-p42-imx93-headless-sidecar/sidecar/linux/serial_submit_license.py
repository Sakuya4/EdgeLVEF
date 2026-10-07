#!/usr/bin/env python3
"""Receive a secret over the diagnostic UART and forward it to board-local IPC.

No command-line secret arguments or content-bearing output. Optional --provision
stores the credential outside source/Git, accessible only to Linux root.
"""
import os
import hmac
import stat
import select
import socket
import struct
import termios
import time
import tty
import sys


def main() -> int:
    fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    original = termios.tcgetattr(fd)
    payload = bytearray()
    header = bytearray()
    deadline = time.monotonic() + 20

    def receive_into(destination: bytearray, count: int) -> None:
        while len(destination) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise TimeoutError()
            destination.extend(os.read(fd, count - len(destination)))

    try:
        tty.setraw(fd)
        os.write(fd, b'LICENSE_INPUT_READY\n')
        termios.tcdrain(fd)
        receive_into(header, 2)
        length = struct.unpack('>H', header)[0]
        if not 1 <= length <= 256:
            raise ValueError()
        receive_into(payload, length)
        if '--verify-only' in sys.argv:
            descriptor = os.open('/var/lib/aco-sidecar/secrets/p42.license', os.O_RDONLY | os.O_NOFOLLOW)
            stored = bytearray()
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
                    raise PermissionError()
                stored.extend(os.read(descriptor, 257))
                equal = hmac.compare_digest(payload, stored)
            finally:
                stored[:] = b'\x00' * len(stored)
                os.close(descriptor)
            os.write(fd, b'LICENSE_BOARD_COPY_MATCH\n' if equal else b'LICENSE_BOARD_COPY_MISMATCH\n')
            termios.tcdrain(fd)
            return 0 if equal else 2
        if '--provision' in sys.argv:
            directory = '/var/lib/aco-sidecar/secrets'
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            path = directory + '/p42.license'
            descriptor = os.open(path + '.new', os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(path + '.new', path)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
            channel.settimeout(3)
            channel.connect('/run/aco-ipc/license.sock')
            channel.sendall(header)
            channel.sendall(payload)
        os.write(fd, b'LICENSE_IPC_DELIVERED\n')
        termios.tcdrain(fd)
        return 0
    except Exception:
        # Neither exception messages nor secret-derived diagnostics are emitted.
        os.write(fd, b'LICENSE_DELIVERY_FAILED\n')
        termios.tcdrain(fd)
        return 1
    finally:
        payload[:] = b'\x00' * len(payload)
        header[:] = b'\x00' * len(header)
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        os.close(fd)


if __name__ == '__main__':
    raise SystemExit(main())
