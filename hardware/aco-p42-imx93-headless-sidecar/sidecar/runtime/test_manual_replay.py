"""Offline safety checks; no SDK, probe, UART, or real credential access."""
import fcntl
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import replay_manual_connection as replay
import sidecar_supervisor as supervisor


class ReplaySafetyTests(unittest.TestCase):
    def test_state_output_is_allowlisted(self):
        raw = (b'AcoSidecar: STATE:PROBE_SELECTED\n'
               b'Untrusted: private text\n'
               b'AcoSidecar: STATE:NOT_A_PRODUCT_STATE\n')
        with patch.object(replay, 'android', return_value=SimpleNamespace(stdout=raw)):
            self.assertEqual(replay.states('123'), ['PROBE_SELECTED'])

    def test_manual_lock_prevents_supervisor_injection(self):
        with tempfile.NamedTemporaryFile() as fixture:
            fcntl.flock(fixture, fcntl.LOCK_EX | fcntl.LOCK_NB)
            builtin_open = open
            with patch('builtins.open', side_effect=lambda *_: builtin_open(fixture.name, 'a')), \
                    patch.object(supervisor, 'android') as android, \
                    patch.object(supervisor, 'deliver') as deliver:
                self.assertEqual(supervisor.supervise_app(b'123'), b'123')
                android.assert_not_called()
                deliver.assert_not_called()

    def test_lock_release_restores_supervisor(self):
        with tempfile.NamedTemporaryFile() as fixture:
            builtin_open = open
            with patch('builtins.open', side_effect=lambda *_: builtin_open(fixture.name, 'a')), \
                    patch.object(supervisor, 'android', return_value=SimpleNamespace(stdout=b'456')), \
                    patch.object(supervisor, 'deliver') as deliver:
                self.assertEqual(supervisor.supervise_app(b'123'), b'456')
                deliver.assert_called_once()


if __name__ == '__main__':
    unittest.main()
