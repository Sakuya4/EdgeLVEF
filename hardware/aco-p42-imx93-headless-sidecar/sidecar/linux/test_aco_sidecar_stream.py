from __future__ import annotations

import socket
import struct
import tempfile
import threading
import unittest

try:
    import cv2
    import numpy as np
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"OpenCV test dependency is unavailable: {exc}")

from aco_sidecar_stream import AcoSidecarStream, MAGIC


class AcoSidecarStreamTest(unittest.TestCase):
    def test_rejects_relative_socket_path(self) -> None:
        with self.assertRaises(ValueError):
            AcoSidecarStream("frame.sock")

    def test_reads_one_frame(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        socket_path = f"{temporary.name}/frame.sock"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen(1)

        expected = np.zeros((8, 12, 3), dtype=np.uint8)
        expected[:, :, 1] = 200
        ok, encoded = cv2.imencode(".jpg", expected)
        self.assertTrue(ok)

        def serve() -> None:
            connection, _ = server.accept()
            with connection:
                payload = encoded.tobytes()
                connection.sendall(MAGIC)
                connection.sendall(struct.pack(">I", len(payload)))
                connection.sendall(payload)
            server.close()

        worker = threading.Thread(target=serve)
        worker.start()
        source = AcoSidecarStream(socket_path=socket_path)
        source.open()
        frame = source.read()
        source.close()
        worker.join(timeout=2)

        self.assertEqual(frame.shape, expected.shape)
        self.assertGreater(float(frame[:, :, 1].mean()), 150.0)


if __name__ == "__main__":
    unittest.main()
