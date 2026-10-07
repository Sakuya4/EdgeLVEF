"""Unix-socket frame source for the Android sidecar on the same i.MX93."""

from __future__ import annotations

import os
import socket
import struct
from typing import Optional

import cv2
import numpy as np


MAGIC = b"ACO-SIDECAR/1\n"
MAX_FRAME_BYTES = 2_000_000


class AcoSidecarStream:
    """Read length-prefixed JPEG frames from a board-local Unix socket."""

    def __init__(self, socket_path: str = "/run/aco-ipc/frame.sock") -> None:
        if not os.path.isabs(socket_path) or "\x00" in socket_path:
            raise ValueError("Aco sidecar transport must use an absolute Unix socket path")
        self.socket_path = socket_path
        self._socket: Optional[socket.socket] = None

    def open(self) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(3.0)
        connection.connect(self.socket_path)
        greeting = self._read_exact(connection, len(MAGIC))
        if greeting != MAGIC:
            connection.close()
            raise ConnectionError("unexpected Aco sidecar protocol greeting")
        self._socket = connection

    def read(self) -> np.ndarray:
        if self._socket is None:
            raise RuntimeError("AcoSidecarStream is not open")
        size = struct.unpack(">I", self._read_exact(self._socket, 4))[0]
        if not 0 < size <= MAX_FRAME_BYTES:
            raise ValueError(f"invalid sidecar frame size: {size}")
        encoded = np.frombuffer(self._read_exact(self._socket, size), dtype=np.uint8)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("sidecar returned an undecodable JPEG frame")
        return frame

    def close(self) -> None:
        connection, self._socket = self._socket, None
        if connection is not None:
            connection.close()

    @staticmethod
    def _read_exact(connection: socket.socket, length: int) -> bytes:
        result = bytearray()
        while len(result) < length:
            chunk = connection.recv(length - len(result))
            if not chunk:
                raise ConnectionError("Aco sidecar disconnected")
            result.extend(chunk)
        return bytes(result)
