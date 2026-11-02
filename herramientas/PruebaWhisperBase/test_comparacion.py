import unittest
from unittest.mock import Mock, patch
from prueba_whisper import Benchmark


class ComparisonTests(unittest.TestCase):
    def test_both_receive_identical_audio(self):
        benchmark = Benchmark()
        def local(audio):
            self.assertEqual(audio.read(), b"same-wav")
            return {"texto": "Hola"}
        benchmark.transcribe = Mock(side_effect=local)
        with patch("prueba_whisper.gemini_transcribe", return_value={"texto": "Hola"}) as cloud:
            report = benchmark.compare(b"same-wav", "test-key", True)
        cloud.assert_called_once_with(b"same-wav", "test-key")
        self.assertEqual(report["Whisper base (local)"]["texto"], "Hola")

    def test_cloud_error_preserves_local_text_without_leaking_credentials(self):
        benchmark = Benchmark()
        benchmark.transcribe = Mock(return_value={"texto": "Resultado local"})
        with patch("prueba_whisper.gemini_transcribe", side_effect=RuntimeError("secret-key")):
            report = benchmark.compare(b"audio", "secret-key", True)
        self.assertNotIn("secret-key", str(report))
        self.assertEqual(report["Whisper base (local)"]["texto"], "Resultado local")

    def test_local_only_does_not_call_cloud(self):
        benchmark = Benchmark()
        benchmark.transcribe = Mock(return_value={"texto": "Hola"})
        with patch("prueba_whisper.gemini_transcribe") as cloud:
            benchmark.compare(b"audio", include_gemini=False)
        cloud.assert_not_called()


if __name__ == "__main__":
    unittest.main()
