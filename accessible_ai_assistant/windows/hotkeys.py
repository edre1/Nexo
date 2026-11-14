"""Native global hotkeys using RegisterHotKey; no keyboard hook or admin rights."""
import ctypes
from ctypes import wintypes
import threading
import logging


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
DEFAULT_PROVIDER_SHORTCUT = "Ctrl+Alt+F8"
FUNCTION_KEYS = {f"F{index}": 0x6F + index for index in range(1, 12)}
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT)]


def parse_hotkey(value: str) -> tuple[int, int]:
    pieces = [part.strip().upper() for part in value.split("+")]
    if set(pieces[:-1]) != {"CTRL", "ALT"} or len(pieces) != 3:
        raise ValueError("El atajo debe tener formato Ctrl+Alt+tecla.")
    key = pieces[-1]
    if key in {"ESC", "ESCAPE"}:
        code = 0x1B
    elif len(key) == 1 and key.isascii() and key.isalnum():
        code = ord(key)
    else:
        code = FUNCTION_KEYS.get(key)
    if code is None:
        raise ValueError("Tecla de atajo no compatible.")
    return MOD_CONTROL | MOD_ALT, code


class GlobalHotkeys:
    def __init__(self, listen: str, cancel: str, callback, *, provider: str = DEFAULT_PROVIDER_SHORTCUT):
        self.listen = parse_hotkey(listen)
        self.cancel = parse_hotkey(cancel)
        self.provider = parse_hotkey(provider)
        if len({self.listen, self.cancel, self.provider}) != 3:
            raise ValueError("Los atajos para hablar, cancelar y cambiar de modelo deben ser distintos.")
        self.provider_shortcut = provider
        self.callback = callback
        self.thread_id = 0
        self.ready = threading.Event()
        self.error = ""
        self.thread = None

    def start(self, *, require_provider: bool = False) -> None:
        self.thread = threading.Thread(target=self._run, args=(require_provider,), daemon=True, name="GlobalHotkeys")
        self.thread.start()
        self.ready.wait(3)
        if self.error:
            raise RuntimeError(self.error)

    def _run(self, require_provider: bool) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        registrations = []
        try:
            for hotkey_id, (mods, key) in ((1, self.listen), (2, self.cancel)):
                if not user32.RegisterHotKey(None, hotkey_id, mods, key):
                    raise RuntimeError("No pude registrar un atajo global. Puede estar ocupado por otra aplicación.")
                registrations.append(hotkey_id)
            mods, key = self.provider
            if user32.RegisterHotKey(None, 3, mods | MOD_NOREPEAT, key):
                registrations.append(3)
            elif require_provider:
                raise RuntimeError(f"El atajo {self.provider_shortcut} para cambiar de modelo puede estar ocupado por otra aplicación.")
            else:
                self.callback("provider_hotkey_unavailable")
            self.ready.set()
            msg = MSG()
            events = {1: "listen", 2: "cancel", 3: "switch_provider"}
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in events:
                    self.callback(events[msg.wParam])
        except Exception as exc:
            logging.getLogger("accessible_assistant").error("global_hotkey_failed", exc_info=True)
            self.error = str(exc)
            self.ready.set()
        finally:
            for hotkey_id in registrations:
                user32.UnregisterHotKey(None, hotkey_id)

    def close(self) -> None:
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
        if self.thread is not None and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=1)
