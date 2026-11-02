"""Microphone input and a replaceable transcription adapter."""
from abc import ABC, abstractmethod
from array import array
from io import BytesIO
import threading
import wave

import sounddevice as sd
from ai.base_provider import AIProvider


class SpeechRecognizer(ABC):
    @abstractmethod
    def listen(self, cancel: threading.Event, seconds: int, language: str) -> str:
        pass


class ProviderSpeechRecognizer(SpeechRecognizer):
    """Records locally; sends one short WAV to the selected provider."""
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def listen(self, cancel: threading.Event, seconds: int, language: str) -> str:
        rate = 16000
        block = 1600
        frames: list[bytes] = []
        heard_voice = False
        quiet_blocks = 0
        try:
            with sd.RawInputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block) as stream:
                for _ in range(seconds * 10):
                    if cancel.is_set():
                        raise InterruptedError("Escucha cancelada.")
                    data, _overflow = stream.read(block)
                    frames.append(bytes(data))
                    samples = array("h")
                    samples.frombytes(data)
                    level = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
                    if level > 350:
                        heard_voice = True
                        quiet_blocks = 0
                    elif heard_voice:
                        quiet_blocks += 1
                        if quiet_blocks >= 13:
                            break
        except sd.PortAudioError as exc:
            raise RuntimeError("No pude acceder al micrófono. Revisa el dispositivo de entrada.") from exc
        if cancel.is_set():
            raise InterruptedError("Escucha cancelada.")
        if not heard_voice:
            raise RuntimeError("No detecté voz. Inténtalo de nuevo.")
        output = BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(b"".join(frames))
        return self.provider.transcribe(output.getvalue(), language)


def microphone_status() -> str:
    try:
        devices = sd.query_devices()
        default = sd.default.device[0]
        if default is None or default < 0:
            return "Sin micrófono predeterminado"
        return f"Disponible: {devices[default]['name']}"
    except Exception:
        return "Micrófono no disponible"
