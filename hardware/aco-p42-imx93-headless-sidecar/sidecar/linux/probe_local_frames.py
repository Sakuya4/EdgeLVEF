#!/usr/bin/env python3
"""Board-only IPC decoding/reconnect check. Emits metadata, not image/secret data."""
import time
from aco_sidecar_stream import AcoSidecarStream


def main():
    total = 0
    started = time.monotonic()
    shapes = set()
    for session in range(2):
        reader = AcoSidecarStream()
        try:
            reader.open()
            for _ in range(60):
                frame = reader.read()
                shapes.add(tuple(frame.shape))
                total += 1
        finally:
            reader.close()
        print('IPC session', session + 1, 'decoded frames:', 60, flush=True)
    elapsed = time.monotonic() - started
    print('IPC decoded total:', total, 'shapes:', sorted(shapes),
          'elapsed seconds:', round(elapsed, 2), 'fps:', round(total / elapsed, 2), flush=True)


if __name__ == '__main__':
    main()
