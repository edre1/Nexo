import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from speech.local_output import LocalSpeechOutput


class LocalAudioTests(unittest.TestCase):
    def test_piper_failure_falls_back_without_loop_or_lost_completion(self):
        with patch("speech.local_output.WindowsSpeechOutput") as windows, patch("speech.local_output.PIPER") as path:
            path.exists.return_value = False
            speech = LocalSpeechOutput("piper")
            speech.on_error = Mock()
            try:
                speech.speak_and_wait("Mensaje de prueba", timeout=3)
                self.assertEqual(speech.engine, "windows")
                windows.return_value.speak_and_wait.assert_called_with("Mensaje de prueba", timeout=120)
                speech.on_error.assert_called_once()
            finally:
                speech.close()
                speech.thread.join(2)
