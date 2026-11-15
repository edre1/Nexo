"""Run native audio operations outside the installed application's UI process."""
from contextlib import contextmanager
import faulthandler
import multiprocessing
import time

from config.paths import DATA_ROOT


def _run(task, connection, args):
    # The diagnostic contains Python stack locations, never the audio or messages.
    path = DATA_ROOT / "logs" / "audio-native.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        log = path.open("a", encoding="utf-8")
    except OSError:
        log = None
    with connection:
        try:
            if log:
                faulthandler.enable(file=log)
            task(connection, *args)
        except (EOFError, BrokenPipeError):
            pass
        finally:
            if log:
                faulthandler.disable()
                log.close()


@contextmanager
def audio_process(task, *args):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_run, args=(task, child, args), daemon=True)
    with parent, child:
        process.start()
        child.close()
        try:
            yield parent, process
        finally:
            parent.close()
            process.join(0.2)
            if process.is_alive():
                process.terminate()
                process.join(2)
            if not process.is_alive():
                process.close()


def receive_audio(connection, process, timeout, cancel=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancel is not None and cancel.is_set():
            raise InterruptedError("Escucha cancelada.")
        if connection.poll(0.05):
            try:
                return connection.recv()
            except (EOFError, OSError):
                break
        if not process.is_alive():
            break
    raise RuntimeError("El componente de audio dejó de responder.")
