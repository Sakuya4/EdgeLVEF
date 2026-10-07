"""Inject the legal P42 license over the board-local, non-logging channel."""

from __future__ import annotations

import getpass
import socket
import struct


def main() -> int:
    license_text = getpass.getpass("P42 license: ")
    encoded = bytearray(license_text.encode("utf-8"))
    license_text = ""
    if not 0 < len(encoded) <= 256:
        encoded[:] = b"\x00" * len(encoded)
        raise ValueError("license length is outside the accepted range")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(3.0)
            connection.connect("/run/aco-ipc/license.sock")
            connection.sendall(struct.pack(">H", len(encoded)))
            connection.sendall(encoded)
    finally:
        encoded[:] = b"\x00" * len(encoded)
    print("License delivered to the on-board sidecar without logging its value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
