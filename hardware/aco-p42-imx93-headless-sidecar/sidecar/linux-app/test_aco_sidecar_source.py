"""Local-only framing, reconnect, invalid payload and cancellation tests."""
import os
import socket
import struct
import tempfile
import threading
import unittest

import cv2
import numpy as np

from sources.aco_sidecar_source import AcoSidecarSource


class SidecarSourceTests(unittest.TestCase):
    def test_absent_sidecar_stays_waiting(self):
        source = AcoSidecarSource('/run/aco-ipc/nonexistent-test.sock')
        source.open()
        self.assertIsNone(source.read())
        source.close()
        self.assertIsNone(source.read())

    def test_reject_remote_transport(self):
        for path in ('http://probe', 'localhost:1234', 'relative.sock'):
            with self.assertRaises(ValueError):
                AcoSidecarSource(path)

    def test_frames_disconnect_reconnect_and_invalid_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'frame.sock')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(path)
                server.listen(1)
                _, encoded = cv2.imencode('.jpg', np.full((12, 16, 3), 123, dtype=np.uint8))
                data = encoded.tobytes()
                def send():
                    for size in (len(data), len(data), 2_000_001):
                        with server.accept()[0] as connection:
                            message = b'ACO-SIDECAR/1\n' + struct.pack('>I', size)
                            if size == len(data):
                                message += data
                            for position in range(0, len(message), 7):
                                connection.sendall(message[position:position + 7])
                worker = threading.Thread(target=send)
                worker.start()
                source = AcoSidecarSource(path)
                source.open()
                self.assertEqual(source.read().shape, (12, 16, 3))
                self.assertIsNone(source.read())
                source._retry_at = 0
                self.assertEqual(source.read().shape, (12, 16, 3))
                self.assertIsNone(source.read())
                source._retry_at = 0
                self.assertIsNone(source.read())
                source.close()
                worker.join(3)
                self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
