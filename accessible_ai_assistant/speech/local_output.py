"""Serialized Piper synthesis/playback with local Windows voice on failure."""
from io import BytesIO
from queue import Queue
import threading
import wave
import winsound

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
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                break
            text, done = item
            try:
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
                        winsound.PlaySound(audio.getvalue(), winsound.SND_MEMORY)
                        continue
                    except Exception:
                        self.engine = "windows"
                        warning = "Piper no está disponible. Usaré la voz de Windows. Puedes descargar los modelos en Configuración."
                        self.fallback.speak(warning)
                        if self.on_error and not self.closed:
                            self.on_error(warning)
                self.fallback.speak_and_wait(text, timeout=120)
            except Exception:
                if self.on_error and not self.closed:
                    self.on_error("No pude reproducir la voz. Revisa la salida de audio de Windows.")
            finally:
                if done:
                    done.set()

    def speak(self, text):
        if text and not self.closed:
            self.queue.put((text[:4000], None))

    def speak_and_wait(self, text, timeout=60):
        done = threading.Event()
        self.queue.put((text[:4000], done))
        if not done.wait(timeout):
            raise RuntimeError("La lectura de voz está tardando demasiado.")

    def close(self):
        self.closed = True
        self.queue.put(None)
        self.fallback.close()
