#!/usr/bin/env python3
"""Board deployment receiver: acknowledged CRC blocks, final SHA256, timeout recovery."""
import base64
import hashlib
import os
from pathlib import Path
import select
import sys
import termios
import time
import tty
import zlib


def receive(target: Path, size: int, expected: str, baud: int) -> None:
    fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    original = termios.tcgetattr(fd)
    buffered = bytearray()

    def send(message: str) -> None:
        os.write(fd, (message + '\n').encode('ascii'))
        termios.tcdrain(fd)

    def line() -> bytes:
        deadline = time.monotonic() + 25
        while b'\n' not in buffered:
            if len(buffered) > 8192:
                raise ValueError('oversized transfer packet')
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise TimeoutError('packet timeout')
            buffered.extend(os.read(fd, 8192))
        end = buffered.index(b'\n')
        result = bytes(buffered[:end])
        del buffered[:end + 1]
        return result

    try:
        tty.setraw(fd)
        send('RX_READY')
        if line() != b'GO':
            raise ValueError('missing GO handshake')
        fast = termios.tcgetattr(fd)
        fast[4] = fast[5] = getattr(termios, 'B' + str(baud))
        termios.tcsetattr(fd, termios.TCSADRAIN, fast)
        time.sleep(0.5)
        send('RX_START')
        digest = hashlib.sha256()
        partial = target.with_name(target.name + '.part')
        received = partial.stat().st_size if partial.exists() else 0
        if received > size or (received != size and received % 4096):
            raise ValueError('invalid partial-file boundary')
        if received:
            with partial.open('rb') as existing:
                for block in iter(lambda: existing.read(65536), b''):
                    digest.update(block)
        send(f'RX_RESUME {received} {digest.hexdigest()}')
        sequence = received // 4096
        with partial.open('ab') as output:
            while received < size:
                fields = line().split(b' ', 2)
                if len(fields) != 3:
                    raise ValueError('malformed packet')
                index, crc, encoded = fields
                block = base64.b64decode(encoded, validate=True)
                if int(index) != sequence or not 0 < len(block) <= 4096:
                    raise ValueError('sequence or block length invalid')
                if f'{zlib.crc32(block):08x}'.encode() != crc:
                    send(f'RX_RETRY {sequence}')
                    continue
                if received + len(block) > size:
                    raise ValueError('excess payload')
                output.write(block)
                digest.update(block)
                received += len(block)
                send(f'RX_ACK {sequence}')
                sequence += 1
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != expected:
            raise ValueError('final SHA256 mismatch')
        os.replace(partial, target)
        send('RX_DONE ' + expected)
        if line() != b'BYE':
            raise ValueError('missing completion handshake')
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        os.close(fd)


if __name__ == '__main__':
    receive(Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
