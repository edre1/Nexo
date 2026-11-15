"""Microphone input and a replaceable transcription adapter."""
from abc import ABC, abstractmethod
from array import array
from io import BytesIO
import sys
import threading
import wave

import sounddevice as sd
from ai.base_provider import AIProvider
from speech.audio_process import audio_process, receive_audio


class SpeechRecognizer(ABC):
    @abstractmethod
    def listen(self, cancel: threading.Event, seconds: int, language: str, on_ready=None, on_recorded=None) -> str:
        pass


class ProviderSpeechRecognizer(SpeechRecognizer):
    """Records locally; sends one short WAV to the selected provider."""
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def listen(self, cancel: threading.Event, seconds: int, language: str, on_ready=None, on_recorded=None) -> str:
        if getattr(sys, "frozen", False):
            with audio_process(microphone_worker, seconds) as (connection, process):
                kind, payload = receive_audio(connection, process, 12, cancel)
                if kind == "ready":
                    if on_ready:
                        on_ready()
                    if cancel.is_set():
                        raise InterruptedError("Escucha cancelada.")
                    connection.send(True)
                    kind, payload = receive_audio(connection, process, min(60, seconds) + 12, cancel)
                if kind != "recording":
                    raise RuntimeError(payload)
                frames, heard_voice = payload
        else:
            frames, heard_voice = self._record(cancel, seconds, on_ready)
        if cancel.is_set():
            raise InterruptedError("Escucha cancelada.")
        if on_recorded:
            on_recorded()
        if not heard_voice:
            raise RuntimeError("No detecté voz. Inténtalo de nuevo.")
        output = BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"".join(frames))
        text = self.provider.transcribe(output.getvalue(), language)
        if cancel.is_set():
            raise InterruptedError("Escucha cancelada.")
        return text

    @staticmethod
    def _record(cancel, seconds, on_ready):
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
        return frames, heard_voice


def microphone_worker(connection, seconds):
    def ready():
        connection.send(("ready", None))
        connection.recv()

    try:
        recording = ProviderSpeechRecognizer._record(threading.Event(), seconds, ready)
    except RuntimeError as exc:
        connection.send(("error", str(exc)))
    else:
        connection.send(("recording", recording))


def microphone_status() -> str:
    try:
        devices = sd.query_devices()
        default = sd.default.device[0]
        if default is None or default < 0:
            return "Sin micrófono predeterminado"
        return f"Disponible: {devices[default]['name']}"
    except Exception:
        return "Micrófono no disponible"
