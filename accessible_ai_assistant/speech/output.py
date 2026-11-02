"""Short local Windows SAPI announcements, serialized to coexist with NVDA."""
from abc import ABC, abstractmethod
from queue import Empty, Queue
import threading


class SpeechOutput(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class WindowsSpeechOutput(SpeechOutput):
    def __init__(self):
        self.queue: Queue[tuple[str, threading.Event | None] | None] = Queue()
        self.ready = threading.Event()
        self.error = ""
        self.thread = threading.Thread(target=self._run, daemon=True, name="WindowsSpeech")
        self.thread.start()
        self.ready.wait(3)

    def _run(self):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Rate = 1
            self.ready.set()
            while True:
                try:
                    item = self.queue.get(timeout=0.2)
                except Empty:
                    continue
                if item is None:
                    break
                text, done = item
                try:
                    voice.Speak(text)
                except Exception:
                    self.error = "La voz de Windows no está disponible."
                finally:
                    if done:
                        done.set()
            del voice
        except Exception:
            self.error = "La voz de Windows no está disponible."
            self.ready.set()
        finally:
            pythoncom.CoUninitialize()

    def speak(self, text: str) -> None:
        if text and not self.error:
            self.queue.put((text[:600], None))

    def speak_and_wait(self, text: str, timeout: float = 10) -> None:
        if self.error:
            raise RuntimeError(self.error)
        done = threading.Event()
        self.queue.put((text[:600], done))
        if not done.wait(timeout) or self.error:
            raise RuntimeError("No pude reproducir la voz de Windows.")

    def close(self) -> None:
        self.queue.put(None)
