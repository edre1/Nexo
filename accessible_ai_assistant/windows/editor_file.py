"""Read VS Code's active path and buffer through its keyboard commands."""
from pathlib import Path
import time

import win32clipboard
import win32gui
from pywinauto.keyboard import send_keys
from windows.windows_controller import WindowsController


def clipboard_text():
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) else ""
    finally:
        win32clipboard.CloseClipboard()


def editor_snapshot(target=None):
    original = clipboard_text()
    try:
        return _editor_snapshot(target)
    finally:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            if original:
                win32clipboard.SetClipboardText(original, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()


def _editor_snapshot(target):
    if target:
        WindowsController(0).activate_target(target)
    if "Visual Studio Code" not in win32gui.GetWindowText(win32gui.GetForegroundWindow()):
        raise ValueError("Activa el archivo en Visual Studio Code y vuelve a pedir la corrección.")
    # VS Code's default shortcut copies the full path without changing the file.
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
    finally:
        win32clipboard.CloseClipboard()
    send_keys("^k^+c")
    time.sleep(0.3)
    path = Path(clipboard_text().strip())
    if not path.is_absolute() or not path.is_file():
        raise ValueError("No pude obtener la ruta del archivo. Guarda el archivo en VS Code.")
    if path.stat().st_size > 400000:
        raise ValueError("El archivo es demasiado grande para esta lectura.")
    disk = path.read_text(encoding="utf-8-sig")
    send_keys("^1^a^c")
    time.sleep(0.2)
    buffer = clipboard_text()
    send_keys("^u")
    if len(buffer) > 100000 or len(disk) > 100000:
        raise ValueError("El archivo es demasiado grande para esta lectura.")
    normalize = lambda text: text.replace("\r\n", "\n")
    return {"path": str(path), "text": buffer, "disk_text": disk, "unsaved": normalize(buffer) != normalize(disk)}
