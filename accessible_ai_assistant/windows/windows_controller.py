"""Fixed Windows operations. Executable paths and key sequences are hard coded."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import time

import win32con
import win32gui
import win32process
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from actions.action_registry import APPLICATIONS


KEYEVENTF_KEYUP = 0x0002


def _escape_literal(text: str) -> str:
    # pywinauto's parser uses these characters for modifiers and key names.
    escapes = {"{": "{{}", "}": "{}}", "+": "{+}", "^": "{^}", "%": "{%}", "~": "{~}", "(": "{(}", ")": "{)}"}
    return "".join(escapes.get(char, char) for char in text.replace("\r\n", "\n"))


KEYS = {
    "CTRL+S": "^s", "CTRL+Z": "^z", "CTRL+Y": "^y", "CTRL+C": "^c",
    "CTRL+V": "^v", "CTRL+A": "^a", "ENTER": "{ENTER}", "TAB": "{TAB}",
    "SHIFT+TAB": "+{TAB}", "ESC": "{ESC}", "UP": "{UP}",
    "DOWN": "{DOWN}", "LEFT": "{LEFT}", "RIGHT": "{RIGHT}",
    "HOME": "{HOME}", "END": "{END}", "BACKSPACE": "{BACKSPACE}",
    "DELETE": "{DELETE}", "F2": "{F2}", "F5": "{F5}",
}


class WindowsController:
    def __init__(self, own_hwnd: int):
        self.own_hwnd = own_hwnd

    def _restore_target(self, hwnd: int) -> None:
        if not hwnd or not win32gui.IsWindow(hwnd) or hwnd == self.own_hwnd:
            raise RuntimeError("No hay una ventana de destino válida. Activa la aplicación e inténtalo de nuevo.")
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            try:
                Desktop(backend="uia").window(handle=hwnd).set_focus()
            except Exception as exc:
                raise RuntimeError("No pude activar la ventana de destino.") from exc
        time.sleep(0.15)
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError("No pude comprobar el foco de la ventana de destino.")

    def activate_target(self, hwnd: int) -> None:
        self._restore_target(hwnd)

    def open_application(self, requested: str) -> str:
        requested = requested.strip().lower()
        name = next((name for name, aliases in APPLICATIONS.items() if requested in aliases), None)
        if name is None:
            raise RuntimeError("Esa aplicación no está en la lista permitida.")
        system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        program = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        candidates = {
            "notepad": [system / "notepad.exe"],
            "explorer": [Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"],
            "calculator": [system / "calc.exe"],
            "chrome": [program / "Google/Chrome/Application/chrome.exe", program_x86 / "Google/Chrome/Application/chrome.exe"],
            "edge": [program_x86 / "Microsoft/Edge/Application/msedge.exe", program / "Microsoft/Edge/Application/msedge.exe"],
            "vscode": [local / "Programs/Microsoft VS Code/Code.exe", program / "Microsoft VS Code/Code.exe"],
        }[name]
        executable = next((path for path in candidates if path.is_file()), None)
        if executable is None and name in {"chrome", "edge", "vscode"}:
            found = shutil.which({"chrome": "chrome.exe", "edge": "msedge.exe", "vscode": "Code.exe"}[name])
            if found:
                executable = Path(found)
        if executable is None:
            raise FileNotFoundError("No encontré esa aplicación instalada.")
        before: set[int] = set()
        def matching(hwnd: int, pid: int | None = None) -> bool:
            if not win32gui.IsWindowVisible(hwnd) or hwnd == self.own_hwnd:
                return False
            title = win32gui.GetWindowText(hwnd).casefold()
            if pid and win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
                return True
            words = {
                "notepad": ("notepad", "bloc de notas"),
                "chrome": ("chrome",),
                "vscode": ("visual studio code",),
                "edge": ("microsoft edge",),
                "explorer": (),
                "calculator": ("calculator", "calculadora"),
            }[name]
            return any(word in title for word in words)
        win32gui.EnumWindows(lambda hwnd, _param: before.add(hwnd) if matching(hwnd) else None, None)
        process = subprocess.Popen([str(executable)], close_fds=True)
        for _ in range(30):
            time.sleep(0.1)
            active = win32gui.GetForegroundWindow()
            if matching(active, process.pid) and (active not in before or active != self.own_hwnd):
                return f"{APPLICATIONS[name][1]} abierto."
            if process.poll() is not None and process.returncode not in (0, None):
                raise RuntimeError("La aplicación no se pudo abrir.")
        if process.poll() is None or process.returncode == 0:
            return f"{APPLICATIONS[name][1]} iniciado. Comprueba si su ventana ya apareció."
        raise RuntimeError("No pude verificar que se abrió la aplicación.")

    def close_application(self, hwnd: int) -> str:
        if hwnd == self.own_hwnd or not win32gui.IsWindow(hwnd):
            raise RuntimeError("No hay una aplicación que pueda cerrar.")
        title = win32gui.GetWindowText(hwnd) or "la aplicación"
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return f"Solicité cerrar {title}. Si hay cambios sin guardar, revisa el diálogo de confirmación."

    def write_text(self, hwnd: int, text: str) -> str:
        self._restore_target(hwnd)
        send_keys(_escape_literal(text), with_spaces=True, with_tabs=True, with_newlines=True, pause=0.05, vk_packet=True)
        return "Texto escrito en la ventana activa."

    def press_key(self, hwnd: int, key: str) -> str:
        normalized = key.upper().replace("CONTROL", "CTRL").replace(" ", "")
        self._restore_target(hwnd)
        send_keys(KEYS[normalized], pause=0.03)
        return f"Tecla {normalized} presionada."

    def move_cursor(self, hwnd: int, direction: str, count: int = 1) -> str:
        self._restore_target(hwnd)
        keys = {
            "left": "{LEFT}", "right": "{RIGHT}", "up": "{UP}", "down": "{DOWN}",
            "home": "{HOME}", "end": "{END}",
            "document_start": "^{HOME}", "document_end": "^{END}",
        }
        sequence = keys[direction]
        send_keys(sequence * count, pause=0.05)
        descriptions = {
            "left": "a la izquierda", "right": "a la derecha",
            "up": "hacia arriba", "down": "hacia abajo",
            "home": "al inicio de la línea", "end": "al final de la línea",
            "document_start": "al inicio del documento", "document_end": "al final del documento",
        }
        if direction in {"home", "end", "document_start", "document_end"}:
            return f"Moví el cursor {descriptions[direction]}."
        return f"Moví el cursor {count} {'posición' if count == 1 else 'posiciones'} {descriptions[direction]}."

    def save_file(self, hwnd: int) -> str:
        self._restore_target(hwnd)
        send_keys("^s")
        time.sleep(0.4)
        foreground = win32gui.GetForegroundWindow()
        if foreground != hwnd:
            return "Abrí el diálogo de guardar. Elige nombre y ubicación, y confirma con el teclado."
        return "Envié la orden de guardar. Confirma en la aplicación que el archivo quedó guardado."

    def volume(self, action: str) -> str:
        key = {"volume_up": 0xAF, "volume_down": 0xAE, "mute_volume": 0xAD}[action]
        ctypes.windll.user32.keybd_event(key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return {"volume_up": "Subí el volumen.", "volume_down": "Bajé el volumen.", "mute_volume": "Cambié el estado de silencio."}[action]
