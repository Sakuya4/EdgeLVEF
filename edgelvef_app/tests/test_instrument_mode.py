import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from core.measurement_session import MeasurementSession
from gpio.reset_button import GPIOResetButton, dispatch_reset_key, is_reset_key
from ui.instrument_layout import SCREEN_HEIGHT, SCREEN_WIDTH, STATS_HEIGHT, minimum_content_size


class MeasurementSessionTests(unittest.TestCase):
    def test_initial_values_are_empty(self):
        session = MeasurementSession()
        self.assertEqual(session.count, 0)
        self.assertIsNone(session.maximum)
        self.assertIsNone(session.minimum)
        self.assertIsNone(session.average)

    def test_max_min_and_average(self):
        session = MeasurementSession()
        for value in (50, 60, 40):
            self.assertTrue(session.update(value))
        self.assertEqual(session.maximum, 60)
        self.assertEqual(session.minimum, 40)
        self.assertEqual(session.average, 50)
        self.assertEqual(session.count, 3)

    def test_reset_clears_everything(self):
        session = MeasurementSession()
        session.update(55)
        session.reset()
        self.assertEqual(session.count, 0)
        self.assertIsNone(session.maximum)
        self.assertIsNone(session.minimum)
        self.assertIsNone(session.average)

    def test_invalid_values_do_not_enter_statistics(self):
        session = MeasurementSession()
        for value in (None, math.nan, math.inf, -math.inf, -1, 101, "50", True, object()):
            self.assertFalse(session.update(value), repr(value))
        self.assertEqual(session.count, 0)


class ResetInputTests(unittest.TestCase):
    def test_keyboard_r_is_reset_fallback(self):
        self.assertTrue(is_reset_key("r"))
        self.assertTrue(is_reset_key("R"))
        self.assertFalse(is_reset_key("Escape"))
        calls = []
        self.assertTrue(dispatch_reset_key("R", lambda: calls.append("reset")))
        self.assertFalse(dispatch_reset_key("Escape", lambda: calls.append("wrong")))
        self.assertEqual(calls, ["reset"])

    def test_gpio_import_failure_is_nonfatal(self):
        callbacks = []
        button = GPIOResetButton("/dev/gpiochip-test", 7, lambda: callbacks.append(True))
        with patch("gpio.reset_button.importlib.import_module", side_effect=ImportError("no gpiod")):
            self.assertFalse(button.start())
        button.close()
        self.assertEqual(callbacks, [])

    def test_unconfigured_gpio_is_nonfatal(self):
        button = GPIOResetButton("", -1, lambda: None)
        self.assertFalse(button.start())
        button.close()


class InstrumentLayoutTests(unittest.TestCase):
    def test_480x320_layout_minimum_fits(self):
        self.assertEqual((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (480, 320))
        self.assertEqual((SCREEN_WIDTH, SCREEN_HEIGHT), (480, 320))
        minimum_width, minimum_height = minimum_content_size()
        self.assertLessEqual(minimum_width, SCREEN_WIDTH)
        self.assertLessEqual(minimum_height, SCREEN_HEIGHT)
        self.assertGreaterEqual(STATS_HEIGHT, 70)
        self.assertLessEqual(STATS_HEIGHT, 85)

    def test_gui_has_no_removed_controls(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertNotIn("Gtk.ComboBox", source)
        self.assertNotIn('Gtk.Button(label="Save")', source)
        self.assertIn("self.fullscreen()", source)
        self.assertIn("set_decorated(False)", source)


class AutostartTests(unittest.TestCase):
    def test_service_has_bounded_restart(self):
        service = (ROOT / "deployment" / "edgelvef.service").read_text(encoding="utf-8")
        self.assertIn("After=weston.service graphical.target", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("RestartSec=2", service)
        script = (ROOT / "run.sh").read_text(encoding="utf-8")
        self.assertIn("/tmp/.X11-unix/X0", script)
        self.assertIn('attempt" -lt 60', script)
