import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.video_session import VideoSessionManager, discover_videos


class FakeSource:
    requires_external_pacing = True

    def __init__(self, path):
        self.path = path
        self.closed = False

    def open(self):
        if self.path.name == "invalid.avi":
            raise RuntimeError("unsupported codec")

    def read(self):
        if self.path.name == "undecodable.mov":
            return None
        return np.full((2, 2, 3), 1 if self.path.name == "first.avi" else 2, dtype=np.uint8)

    def get_fps(self):
        return 30 if self.path.name == "first.avi" else 25

    def close(self):
        self.closed = True


class DiscoveryTests(unittest.TestCase):
    def test_extensions_sorting_and_files_only(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            root = Path(temp)
            for name in ["patient02.avi", "plax.avi", "patient01.avi", "clip.MP4", "other.mov", "other.mkv", "ignore.txt"]:
                (root / name).touch()
            (root / "directory.avi").mkdir()
            self.assertEqual(
                [path.name for path in discover_videos(root)],
                ["clip.MP4", "other.mkv", "other.mov", "patient01.avi", "patient02.avi", "plax.avi"],
            )

    def test_missing_directory_is_empty(self):
        self.assertEqual(discover_videos(ROOT / "missing-test-directory"), [])


class SwitchingTests(unittest.TestCase):
    def setUp(self):
        self.manager = VideoSessionManager(5, 30, FakeSource)
        # Do not race actual acquisition; lifecycle and cleanup are tested here.
        self.start_patch = patch("core.video_session.VideoWorker.start")
        self.start_patch.start()

    def tearDown(self):
        self.manager.stop()
        self.start_patch.stop()

    def test_switch_clears_old_buffer_and_mailbox_and_updates_fps(self):
        first, error = self.manager.switch(Path("first.avi"), lambda msg: None)
        self.assertIsNone(error)
        second, error = self.manager.switch(Path("second.avi"), lambda msg: None)
        self.assertIsNone(error)
        self.assertTrue(first.worker.source.closed)
        self.assertEqual(len(first.buffer), 0)
        self.assertIsNone(first.worker.pop_latest())
        self.assertIsNot(first.buffer, second.buffer)
        self.assertEqual(second.buffer.max_frames, 125)
        self.assertEqual([int(item.frame[0, 0, 0]) for item in second.buffer.snapshot()], [2])

    def test_invalid_codec_rolls_back_with_fresh_buffer(self):
        first, _ = self.manager.switch(Path("first.avi"), lambda msg: None)
        restored, error = self.manager.switch(Path("invalid.avi"), lambda msg: None)
        self.assertIsNotNone(error)
        self.assertEqual(restored.path.name, "first.avi")
        self.assertEqual(len(first.buffer), 0)
        self.assertIsNot(first.buffer, restored.buffer)

    def test_undecodable_first_frame_returns_error_without_crashing(self):
        session, error = self.manager.switch(Path("undecodable.mov"), lambda msg: None)
        self.assertIsNone(session)
        self.assertIsNotNone(error)
        valid, error = self.manager.switch(Path("first.avi"), lambda msg: None)
        self.assertIsNotNone(valid)
        self.assertIsNone(error)


class LauncherTests(unittest.TestCase):
    def test_launcher_and_desktop_targets(self):
        script = (ROOT / "run.sh").read_text()
        self.assertIn("exec python3 -u main.py", script)
        self.assertIn("export GDK_BACKEND=x11", script)
        self.assertIn("exec python3 -u main.py", script)
        entry = (ROOT / "deployment" / "edgelvef.desktop").read_text()
        self.assertIn("Exec=/opt/edgelvef_app/run.sh", entry)
        self.assertIn("Terminal=false", entry)
