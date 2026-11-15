"""Serialized Piper synthesis/playback with local Windows voice on failure."""
from io import BytesIO
from queue import Queue
from tempfile import TemporaryDirectory
from pathlib import Path
import threading
import wave
import winsound
import logging
import sys
from contextlib import ExitStack

from speech.local_models import PIPER
from speech.output import WindowsSpeechOutput
from speech.audio_process import audio_process, receive_audio


def piper_worker(connection, model):
    from piper import PiperVoice

    voice = PiperVoice.load(model, use_cuda=False)
    while True:
        text = connection.recv()
        audio = BytesIO()
        with wave.open(audio, "wb") as wav:
            voice.synthesize_wav(text, wav)
        connection.send(audio.getvalue())


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
        with ExitStack() as processes:
            self._speak_loop(processes)

    def _speak_loop(self, processes):
        piper = None
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
                        if not PIPER.exists():
                            raise ValueError("Falta la voz de Piper. Descarga los modelos desde Configuración.")
                        if getattr(sys, "frozen", False):
                            if piper is None:
                                piper = processes.enter_context(audio_process(piper_worker, str(PIPER)))
                            connection, process = piper
                            connection.send(text)
                            audio = BytesIO(receive_audio(connection, process, 45))
                        else:
                            if self.voice is None:
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
                        processes.close()
                        piper = None
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
