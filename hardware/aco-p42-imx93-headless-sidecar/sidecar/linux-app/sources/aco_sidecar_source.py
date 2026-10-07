"""Reconnectable board-local Android JPEG source. No TCP or remote fallback."""
import os
import socket
import struct
import threading
import time

import cv2
import numpy as np

from sources.source_base import UltrasoundSource


class AcoSidecarSource(UltrasoundSource):
    may_start_without_frame = True
    requires_external_pacing = False
    display_name = "On-board Aco P42"

    def __init__(self, socket_path="/run/aco-ipc/frame.sock", fps=20):
        if not os.path.isabs(socket_path) or "\x00" in socket_path:
            raise ValueError("An absolute board-local Unix socket is required")
        self.socket_path = socket_path
        self.fps = fps
        self._socket = None
        self._closed = threading.Event()
        self._retry_at = 0
        self._live = False

    def open(self):
        self._closed.clear()

    def get_fps(self):
        return self.fps

    @property
    def is_live(self):
        return self._live

    @staticmethod
    def _exact(connection, length):
        data = bytearray()
        while len(data) < length:
            chunk = connection.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Sidecar disconnected")
            data.extend(chunk)
        return data

    def _disconnect(self):
        connection, self._socket = self._socket, None
        if connection:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

    def read(self):
        if self._closed.is_set() or time.monotonic() < self._retry_at:
            return None
        try:
            if self._socket is None:
                connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._socket = connection
                connection.settimeout(3)
                connection.connect(self.socket_path)
                if self._exact(connection, len(b"ACO-SIDECAR/1\n")) != b"ACO-SIDECAR/1\n":
                    raise ValueError("Sidecar protocol mismatch")
            size = struct.unpack(">I", self._exact(self._socket, 4))[0]
            if not 0 < size <= 2_000_000:
                raise ValueError("Invalid Sidecar frame length")
            encoded = np.frombuffer(self._exact(self._socket, size), dtype=np.uint8)
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Invalid Sidecar JPEG")
            if not self._live:
                print("SIDECAR_FRAME_LIVE", flush=True)
            self._live = True
            return frame
        except (OSError, ValueError, ConnectionError, AttributeError):
            self._disconnect()
            if self._live:
                print("SIDECAR_FRAME_WAITING: reconnecting locally", flush=True)
            self._live = False
            self._retry_at = time.monotonic() + 1
            return None

    def close(self):
        self._closed.set()
        self._disconnect()
