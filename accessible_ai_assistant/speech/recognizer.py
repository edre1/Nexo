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
    def listen(self, cancel: threading.Event, seconds: int, language: str, on_ready=None) -> str:
        pass


class ProviderSpeechRecognizer(SpeechRecognizer):
    """Records locally; sends one short WAV to the selected provider."""
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def listen(self, cancel: threading.Event, seconds: int, language: str, on_ready=None) -> str:
        rate = 16000
        block = 1600
        frames: list[bytes] = []
        heard_voice = False
        quiet_blocks = 0
        try:
            with sd.RawInputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block) as stream:
                if on_ready:
                    on_ready()
                    # Discard the assistant's spoken cue before recording the user.
                    pending = stream.read_available
                    if pending:
                        stream.read(pending)
                for _ in range(max(1, min(60, seconds)) * 10):
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
                    else:
                        quiet_blocks += 1
                        if quiet_blocks >= 30:
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
        text = self.provider.transcribe(output.getvalue(), language)
        if cancel.is_set():
            raise InterruptedError("Escucha cancelada.")
        return text


def microphone_status() -> str:
    try:
        devices = sd.query_devices()
        default = sd.default.device[0]
        if default is None or default < 0:
            return "Sin micrófono predeterminado"
        return f"Disponible: {devices[default]['name']}"
    except Exception:
        return "Micrófono no disponible"
