"""Native global hotkeys using RegisterHotKey; no keyboard hook or admin rights."""
import ctypes
from ctypes import wintypes
import threading


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
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
    code = 0x1B if key in {"ESC", "ESCAPE"} else ord(key) if len(key) == 1 and key.isascii() and key.isalnum() else None
    if code is None:
        raise ValueError("Tecla de atajo no compatible.")
    return MOD_CONTROL | MOD_ALT, code


class GlobalHotkeys:
    def __init__(self, listen: str, cancel: str, callback):
        self.listen = parse_hotkey(listen)
        self.cancel = parse_hotkey(cancel)
        self.callback = callback
        self.thread_id = 0
        self.ready = threading.Event()
        self.error = ""
        self.thread = threading.Thread(target=self._run, daemon=True, name="GlobalHotkeys")

    def start(self) -> None:
        self.thread.start()
        self.ready.wait(3)
        if self.error:
            raise RuntimeError(self.error)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        registrations = []
        try:
            for hotkey_id, (mods, key) in ((1, self.listen), (2, self.cancel)):
                if not user32.RegisterHotKey(None, hotkey_id, mods, key):
                    raise RuntimeError("No pude registrar un atajo global. Puede estar ocupado por otra aplicación.")
                registrations.append(hotkey_id)
            self.ready.set()
            msg = MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.callback("listen" if msg.wParam == 1 else "cancel")
        except Exception as exc:
            self.error = str(exc)
            self.ready.set()
        finally:
            for hotkey_id in registrations:
                user32.UnregisterHotKey(None, hotkey_id)

    def close(self) -> None:
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
