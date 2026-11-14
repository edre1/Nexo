import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import load_settings, save_listen_hotkey
from windows.hotkeys import GlobalHotkeys


class PreferenceTests(unittest.TestCase):
    def test_advanced_mode_and_voice_review_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            self.assertFalse(load_settings().advanced_mode)
            self.assertFalse(load_settings().review_transcript)
            save_listen_hotkey("Ctrl+Alt+A", advanced_mode=True, review_transcript=True)
            self.assertTrue(load_settings().advanced_mode)
            self.assertTrue(load_settings().review_transcript)

    def test_provider_shortcut_defaults_to_f8_and_survives_other_edits(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            self.assertEqual(load_settings().hotkey_provider, "Ctrl+Alt+F8")
            save_listen_hotkey("Ctrl+Alt+A", hotkey_provider="Ctrl+Alt+F9")
            save_listen_hotkey("Ctrl+Alt+J")
            self.assertEqual(load_settings().hotkey_provider, "Ctrl+Alt+F9")

    def test_shortcuts_for_different_actions_cannot_use_the_same_key(self):
        with self.assertRaisesRegex(ValueError, "deben ser distintos"):
            GlobalHotkeys("Ctrl+Alt+J", "Ctrl+Alt+Escape", None, provider="Alt+Ctrl+j")

    def test_luna_is_the_default_provider(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            self.assertEqual(load_settings().ai_provider, "openai")

    def test_confirmation_preference_defaults_on_and_survives_other_edits(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            self.assertTrue(load_settings().require_confirmation_for_sensitive_actions)
            save_listen_hotkey("Ctrl+Alt+J", confirm_actions=False)
            save_listen_hotkey("Ctrl+Alt+K")
            self.assertFalse(load_settings().require_confirmation_for_sensitive_actions)
            save_listen_hotkey("Ctrl+Alt+K", confirm_actions=True)
            self.assertTrue(load_settings().require_confirmation_for_sensitive_actions)

    def test_shortcut_survives_reload_without_rewriting_defaults(self):
        with tempfile.TemporaryDirectory() as folder, patch("config.settings.DATA_ROOT", Path(folder)):
            save_listen_hotkey("Ctrl+Alt+J", "provider", "piper")
            self.assertEqual(load_settings().hotkey_listen, "Ctrl+Alt+J")
            self.assertEqual(load_settings().speech_recognition, "provider")
            self.assertEqual(load_settings().speech_output, "piper")
            with self.assertRaises(ValueError):
                save_listen_hotkey("Ctrl+Shift+J")
            self.assertEqual(load_settings().hotkey_listen, "Ctrl+Alt+J")
