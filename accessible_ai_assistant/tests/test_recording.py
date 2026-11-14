from array import array
from io import BytesIO
import threading
import unittest
from unittest.mock import Mock, patch
import wave

from speech.recognizer import ProviderSpeechRecognizer


class Stream:
    def __init__(self, levels, pending=0):
        self.levels = iter(levels)
        self.read_available = pending
        self.sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self, size):
        self.sizes.append(size)
        return array('h', [next(self.levels)] * size).tobytes(), False


class RecordingTests(unittest.TestCase):
    def listen(self, levels, callback=None, pending=0):
        provider = Mock()
        provider.transcribe.return_value = 'Texto reconocido'
        stream = Stream(levels, pending)
        with patch('speech.recognizer.sd.RawInputStream', return_value=stream):
            result = ProviderSpeechRecognizer(provider).listen(threading.Event(), 60, 'es-MX', callback)
        return stream, provider, result

    def test_silence_resets_after_speech_and_stops_after_three_seconds(self):
        stream, provider, result = self.listen([1000] + [0] * 29 + [1000] + [0] * 30)
        self.assertEqual(len(stream.sizes), 61)
        self.assertEqual(result, 'Texto reconocido')
        provider.transcribe.assert_called_once()

    def test_continuous_speech_cannot_exceed_one_minute(self):
        stream, provider, _ = self.listen([1000] * 600)
        self.assertEqual(len(stream.sizes), 600)
        with wave.open(BytesIO(provider.transcribe.call_args.args[0]), 'rb') as wav:
            self.assertEqual(wav.getnframes() / wav.getframerate(), 60)

    def test_ready_callback_discards_its_audio(self):
        callback = Mock()
        stream, provider, _ = self.listen([2000, 1000] + [0] * 30, callback, pending=800)
        callback.assert_called_once()
        self.assertEqual(stream.sizes[0], 800)
        with wave.open(BytesIO(provider.transcribe.call_args.args[0]), 'rb') as wav:
            self.assertEqual(array('h', wav.readframes(1))[0], 1000)

    def test_no_voice_is_not_sent_to_provider(self):
        provider = Mock()
        with patch('speech.recognizer.sd.RawInputStream', return_value=Stream([0] * 30)):
            with self.assertRaisesRegex(RuntimeError, 'No detecté voz'):
                ProviderSpeechRecognizer(provider).listen(threading.Event(), 60, 'es-MX')
        provider.transcribe.assert_not_called()

    def test_recording_finished_is_announced_before_transcription(self):
        provider = Mock()
        stream = Stream([1000] + [0] * 30)
        def recorded():
            provider.transcribe.assert_not_called()
            self.assertEqual(len(stream.sizes), 31)
        with patch("speech.recognizer.sd.RawInputStream", return_value=stream):
            ProviderSpeechRecognizer(provider).listen(threading.Event(), 60, "es-MX", on_recorded=recorded)
        provider.transcribe.assert_called_once()
