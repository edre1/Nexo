"""Serialized Piper synthesis/playback with local Windows voice on failure."""
from io import BytesIO
from queue import Queue
from tempfile import TemporaryDirectory
from pathlib import Path
import threading
import wave
import winsound
import logging

from speech.local_models import PIPER
from speech.output import WindowsSpeechOutput


class LocalSpeechOutput:
    def __init__(self, engine="piper"):
        self.engine = engine
        self.fallback = WindowsSpeechOutput()
        self.voice = None
        self.on_error = None
        self.queue = Queue()
        self.closed = False
        self.announcement = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                break
            text, done, cancelled = item
            try:
                if cancelled and cancelled.is_set():
                    continue
                if self.engine == "piper":
                    try:
                        if self.voice is None:
                            if not PIPER.exists():
                                raise ValueError("Falta la voz de Piper. Descarga los modelos desde Configuración.")
                            from piper import PiperVoice
                            self.voice = PiperVoice.load(str(PIPER), use_cuda=False)
                        audio = BytesIO()
                        with wave.open(audio, "wb") as wav:
                            self.voice.synthesize_wav(text, wav)
                        if cancelled is None:
                            winsound.PlaySound(audio.getvalue(), winsound.SND_MEMORY)
                        elif not cancelled.is_set():
                            audio.seek(0)
                            with wave.open(audio, "rb") as wav:
                                duration = wav.getnframes() / wav.getframerate()
                            with TemporaryDirectory(prefix="nexo-voice-") as folder:
                                path = Path(folder) / "voice.wav"
                                path.write_bytes(audio.getvalue())
                                if not cancelled.is_set():
                                    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                                    try:
                                        cancelled.wait(duration + 0.05)
                                    finally:
                                        winsound.PlaySound(None, 0)
                        continue
                    except Exception:
                        logging.getLogger("accessible_assistant").error("piper_synthesis_failed", exc_info=True)
                        self.engine = "windows"
                        warning = "Piper no está disponible. Usaré la voz de Windows. Puedes descargar los modelos en Configuración."
                        self.fallback.speak(warning)
                        if self.on_error and not self.closed:
                            self.on_error(warning)
                if cancelled is None:
                    self.fallback.speak_and_wait(text, timeout=120)
                else:
                    self.fallback.speak_and_wait(text, timeout=120, cancelled=cancelled)
            except Exception:
                logging.getLogger("accessible_assistant").error("speech_playback_failed", exc_info=True)
                if self.on_error and not self.closed:
                    self.on_error("No pude reproducir la voz. Revisa la salida de audio de Windows.")
            finally:
                if done:
                    done.set()

    def speak(self, text):
        if text and not self.closed:
            self.queue.put((text[:4000], None, self.announcement))

    def interrupt_and_speak(self, text):
        self.announcement.set()
        self.announcement = threading.Event()
        self.speak(text)

    def speak_and_wait(self, text, timeout=60):
        done = threading.Event()
        self.queue.put((text[:4000], done, None))
        if not done.wait(timeout):
            raise RuntimeError("La lectura de voz está tardando demasiado.")

    def close(self):
        self.closed = True
        self.announcement.set()
        self.queue.put(None)
        self.fallback.close()
