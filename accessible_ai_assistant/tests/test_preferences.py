import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import load_settings, save_listen_hotkey


class PreferenceTests(unittest.TestCase):
    def test_shortcut_survives_reload_without_rewriting_defaults(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            save_listen_hotkey("Ctrl+Alt+J", "provider", "piper")
            self.assertEqual(load_settings().hotkey_listen, "Ctrl+Alt+J")
            self.assertEqual(load_settings().speech_recognition, "provider")
            self.assertEqual(load_settings().speech_output, "piper")
            with self.assertRaises(ValueError):
                save_listen_hotkey("Ctrl+Shift+J")
            self.assertEqual(load_settings().hotkey_listen, "Ctrl+Alt+J")
