"""Translate validated computer actions into input scoped to one Windows window."""
import ctypes
from ctypes import wintypes
from io import BytesIO
import math
import os

import mss
from PIL import Image, ImageDraw
import win32api
import win32gui
import win32process
from pywinauto import Desktop, mouse
from pywinauto.keyboard import send_keys

from windows.windows_controller import WindowsController, KEYS, _escape_literal
from windows.ui_automation import UIAutomation

APPS = {"notepad.exe", "chrome.exe", "msedge.exe", "code.exe", "winword.exe", "explorer.exe", "calculatorapp.exe", "calc.exe"}
KEY_MAP = {**KEYS, "CTRL+HOME": "^{HOME}", "CTRL+END": "^{END}", "CTRL+F": "^f", "CTRL+L": "^l", "CTRL+O": "^o", "CTRL+N": "^n", "CTRL+SHIFT+S": "^+s", "CTRL+TAB": "^{TAB}", "CTRL+SHIFT+TAB": "^+{TAB}", "PAGEDOWN": "{PGDN}", "PAGEUP": "{PGUP}", "ALT+LEFT": "%{LEFT}", "ALT+RIGHT": "%{RIGHT}"}
KEY_MAP.pop("DELETE")
DENIED_WORDS = ("eliminar", "delete", "borrar", "comprar", "purchase", "pagar", "checkout", "enviar", "send", "publicar", "publish", "instalar", "install", "ejecutar", "run", "terminal", "powershell", "contraseña", "password", "permisos", "permissions")


def normalized_keys(keys):
    if not isinstance(keys, list) or not 1 <= len(keys) <= 3 or not all(isinstance(k, str) for k in keys):
        raise ValueError("Combinación de teclas no válida.")
    aliases = {"CONTROL": "CTRL", "CONTROL_L": "CTRL", "CTRL_L": "CTRL", "ALT_L": "ALT", "SHIFT_L": "SHIFT", "ARROWLEFT": "LEFT", "ARROWRIGHT": "RIGHT", "ARROWUP": "UP", "ARROWDOWN": "DOWN", "ESCAPE": "ESC", "RETURN": "ENTER"}
    result = "+".join(aliases.get(k.upper(), k.upper()) for k in keys)
    if result not in KEY_MAP:
        raise ValueError("La combinación de teclas solicitada no está permitida.")
    return result


class ComputerDriver:
    def __init__(self, target, own_hwnd, cancel):
        self.target, self.own_hwnd, self.cancel = target, own_hwnd, cancel
        self.controller = WindowsController(own_hwnd)
        self.rect = None
        self._check_process()

    def _check_process(self):
        if not self.target or not win32gui.IsWindow(self.target):
            raise ValueError("Activa primero la ventana que quieres manejar con Luna.")
        pid = win32process.GetWindowThreadProcessId(self.target)[1]
        if pid == os.getpid():
            raise ValueError("El control visual no puede manejar la ventana de Nexo.")
        handle = win32api.OpenProcess(0x1000, False, pid)
        try:
            query = ctypes.windll.kernel32.QueryFullProcessImageNameW
            query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            query.restype = wintypes.BOOL
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if not query(int(handle), 0, buffer, ctypes.byref(length)):
                raise ValueError("No pude comprobar la aplicación de destino.")
        finally:
            handle.Close()
        executable = buffer.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        if executable not in APPS:
            raise ValueError("Esta prueba admite Bloc de notas, Word, Chrome, Edge, VS Code, Explorador y Calculadora.")
        title = win32gui.GetWindowText(self.target).casefold()
        if any(word in title for word in ("powershell", "terminal", "cmd.exe", "contraseña", "password")):
            raise ValueError("No se permite controlar esta ventana.")

    def _activate(self):
        if self.cancel.is_set():
            raise InterruptedError("Control visual cancelado.")
        self._check_process()
        active = win32gui.GetForegroundWindow()
        if active and active != self.target and win32process.GetWindowThreadProcessId(active)[1] != os.getpid():
            raise ValueError("Cambió la ventana activa. Detuve el control visual para no actuar en otra aplicación.")
        self.controller.activate_target(self.target)

    def capture(self):
        self._activate()
        rect = win32gui.GetWindowRect(self.target)
        with mss.mss() as screen:
            monitor = screen.monitors[0]
            left, top = max(rect[0], monitor["left"]), max(rect[1], monitor["top"])
            right = min(rect[2], monitor["left"] + monitor["width"])
            bottom = min(rect[3], monitor["top"] + monitor["height"])
            if right - left < 64 or bottom - top < 64:
                raise ValueError("La ventana no tiene un área visible suficiente.")
            self.rect = (left, top, right, bottom)
            self.window_rect = rect
            raw = screen.grab({"left": left, "top": top, "width": right-left, "height": bottom-top})
            image = Image.frombytes("RGB", raw.size, raw.rgb)
            x, y = win32gui.GetCursorPos()
            if left <= x < right and top <= y < bottom:
                x, y = x-left, y-top
                ImageDraw.Draw(image).ellipse((x-4, y-4, x+4, y+4), outline="#ff00ff", width=2)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _point(self, point):
        if not self.rect:
            raise ValueError("Se necesita una captura antes de mover el ratón.")
        if not isinstance(point, dict):
            raise ValueError("Punto de ratón no válido.")
        x, y = point.get("x"), point.get("y")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
            raise ValueError("Coordenadas no válidas.")
        left, top, right, bottom = self.rect
        if not (0 <= x < right-left and 0 <= y < bottom-top):
            raise ValueError("El punto está fuera de la ventana elegida.")
        return left + int(x), top + int(y)

    def validate(self, action):
        if not isinstance(action, dict) or action.get("type") not in {"click", "double_click", "drag", "move", "scroll", "keypress", "type", "wait", "screenshot"}:
            raise ValueError("Acción visual desconocida.")
        kind = action["type"]
        if kind in {"click", "double_click", "move", "scroll"}:
            self._point(action)
        if kind == "click" and action.get("button", "left") not in {"left", "right"}:
            raise ValueError("Botón de ratón no permitido.")
        if kind == "keypress":
            normalized_keys(action.get("keys"))
        if kind == "type":
            text = action.get("text")
            if not isinstance(text, str) or not 1 <= len(text) <= 2000 or any(word in text.casefold() for word in ("javascript:", "powershell", "cmd.exe", "cmd /", "mshta", "file://")):
                raise ValueError("Texto no permitido para control visual.")
        if kind == "scroll":
            amount = action.get("scroll_amount")
            if action.get("scroll_direction") not in {"up", "down"} or type(amount) is not int or not 0 < amount <= 1200:
                raise ValueError("Desplazamiento no permitido.")
        if kind == "drag":
            path = action.get("path")
            if not isinstance(path, list) or not 2 <= len(path) <= 50:
                raise ValueError("Trayectoria de arrastre no válida.")
            for point in path:
                self._point(point)

    def describe(self, action):
        kind = action["type"]
        if kind == "type":
            return "escribir este texto: " + action["text"]
        if kind == "keypress":
            return "presionar " + normalized_keys(action["keys"])
        if kind in {"click", "double_click"}:
            x, y = self._point(action)
            try:
                name = Desktop(backend="uia").from_point(x, y).element_info.name
            except Exception:
                name = ""
            if name and any(word in name.casefold() for word in DENIED_WORDS):
                raise ValueError("Ese control requiere intervención manual.")
            return f"{'hacer doble clic' if kind == 'double_click' else 'hacer clic'} en {name[:200] if name else 'el punto ' + str((action['x'], action['y']))} de {win32gui.GetWindowText(self.target)}"
        return "arrastrar el ratón dentro de la ventana"

    def execute(self, action):
        self._activate()
        if win32gui.GetWindowRect(self.target) != self.window_rect:
            raise ValueError("La ventana se movió o cambió de tamaño. Solicita una nueva tarea visual.")
        self.validate(action)
        kind = action["type"]
        if kind in {"type", "keypress"}:
            self._check_keyboard_focus()
        points = action["path"] if kind == "drag" else [action] if kind in {"click", "double_click", "move", "scroll"} else []
        for point in points:
            if win32gui.GetAncestor(win32gui.WindowFromPoint(self._point(point)), 2) != self.target:
                raise ValueError("Otra ventana cubre el punto solicitado. Detuve la acción del ratón.")
        if kind in {"click", "double_click"}:
            self.describe(action)  # Recheck the accessible control after confirmation.
            point = self._point(action)
            actual = win32gui.GetAncestor(win32gui.WindowFromPoint(point), 2)
            if actual != self.target:
                raise ValueError("Otra ventana cubre el punto solicitado. Detuve el clic.")
            if kind == "double_click":
                mouse.double_click(coords=point)
            else:
                mouse.click(button=action.get("button", "left"), coords=point)
        elif kind == "move":
            mouse.move(coords=self._point(action))
        elif kind == "type":
            send_keys(_escape_literal(action["text"]), with_spaces=True, with_tabs=True, with_newlines=True, vk_packet=True, pause=0.01)
        elif kind == "keypress":
            send_keys(KEY_MAP[normalized_keys(action["keys"])], pause=0.03)
        elif kind == "scroll":
            mouse.scroll(coords=self._point(action), wheel_dist=max(1, action["scroll_amount"] // 100) * (1 if action["scroll_direction"] == "up" else -1))
        elif kind == "drag":
            path = [self._point(p) for p in action["path"]]
            mouse.press(coords=path[0])
            try:
                for point in path[1:]:
                    if self.cancel.wait(0.05):
                        raise InterruptedError("Arrastre cancelado.")
                    mouse.move(coords=point)
            finally:
                mouse.release()
        elif kind == "wait":
            if self.cancel.wait(0.5):
                raise InterruptedError("Control visual cancelado.")

    def _check_keyboard_focus(self):
        try:
            element = UIAutomation._focused()
            if element.element_info.element.CurrentIsPassword:
                raise ValueError("Los campos de contraseña requieren intervención manual.")
            for _ in range(6):
                if element is None:
                    break
                name = (element.element_info.name or "").casefold()
                if any(word in name for word in ("terminal", "console", "consola", "powershell", "cmd.exe", "password", "contraseña")):
                    raise ValueError("No se permite enviar teclas a terminales ni campos sensibles.")
                element = element.parent()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("No pude comprobar el campo que recibirá las teclas. Selecciónalo manualmente e inténtalo de nuevo.") from exc
