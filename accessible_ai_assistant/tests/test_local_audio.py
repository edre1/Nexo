import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from speech.local_models import WhisperTranscriber
from speech.local_output import LocalSpeechOutput


class LocalAudioTests(unittest.TestCase):
    def test_missing_whisper_never_uses_network(self):
        with patch("speech.local_models.WHISPER", Path("not-installed-model")):
            with self.assertRaisesRegex(ValueError, "Falta Whisper"):
                WhisperTranscriber().transcribe(b"audio", "es-MX")

    def test_whisper_uses_spanish_and_consumes_segments(self):
        transcriber = WhisperTranscriber()
        transcriber.model = Mock()
        transcriber.model.transcribe.return_value = (iter([SimpleNamespace(text=" Hola"), SimpleNamespace(text=" Nexo")]), None)
        with patch("pathlib.Path.exists", return_value=True):
            self.assertEqual(transcriber.transcribe(b"audio", "es-MX"), "Hola Nexo")
        self.assertEqual(transcriber.model.transcribe.call_args.kwargs["language"], "es")

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
