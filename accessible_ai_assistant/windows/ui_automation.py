"""Accessibility tree queries; never uses screen coordinates."""
from dataclasses import dataclass
import win32gui
from pywinauto import Desktop
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_defines import IUIA
from pywinauto.uia_element_info import UIAElementInfo


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str


class UIAutomation:
    @staticmethod
    def _focused():
        return UIAWrapper(UIAElementInfo(IUIA().get_focused_element()))

    def active_window(self) -> WindowInfo:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("No encontré una ventana activa.")
        return WindowInfo(hwnd, win32gui.GetWindowText(hwnd).strip() or "Ventana sin título")

    def _window(self, hwnd: int):
        if not win32gui.IsWindow(hwnd):
            raise RuntimeError("La ventana ya no está disponible.")
        return Desktop(backend="uia").window(handle=hwnd)

    def focused_element(self) -> str:
        try:
            element = self._focused()
            info = element.element_info
            return f"{info.control_type or 'Control'}: {info.name or 'sin nombre'}"
        except Exception as exc:
            raise RuntimeError("No pude consultar el foco mediante UI Automation.") from exc

    def visible_controls(self, hwnd: int, limit: int = 45) -> list[str]:
        try:
            result = []
            seen = set()
            for element in self._window(hwnd).descendants():
                if not element.is_visible():
                    continue
                info = element.element_info
                name = (info.name or "").strip()
                kind = (info.control_type or "Control").strip()
                if not name and kind not in {"Edit", "Document", "Tree", "List", "Tab", "MenuBar", "StatusBar"}:
                    continue
                label = f"{kind}: {name or 'sin nombre'}"
                if label not in seen:
                    result.append(label)
                    seen.add(label)
                if len(result) >= limit:
                    break
            return result
        except Exception as exc:
            raise RuntimeError("No pude leer los controles de esta ventana.") from exc

    def focus_element(self, hwnd: int, name: str) -> str:
        needle = name.casefold().strip()
        try:
            matches = [e for e in self._window(hwnd).descendants() if e.is_visible() and needle in (e.element_info.name or "").casefold()]
            if not matches:
                raise LookupError("No encontré ese control accesible.")
            matches[0].set_focus()
            return matches[0].element_info.name or name
        except LookupError:
            raise
        except Exception as exc:
            raise RuntimeError("No pude colocar el foco en ese control.") from exc

    def get_element_text(self, hwnd: int, name: str) -> str:
        needle = name.casefold().strip()
        for element in self._window(hwnd).descendants():
            if needle == (element.element_info.name or "").casefold():
                try:
                    if element.iface_value:
                        return element.iface_value.CurrentValue
                except Exception:
                    pass
                try:
                    if element.iface_text:
                        return element.iface_text.DocumentRange.GetText(-1)
                except Exception:
                    pass
                return element.window_text()
        raise LookupError("No encontré ese control accesible.")

    def invoke_element(self, hwnd: int, name: str) -> bool:
        needle = name.casefold().strip()
        for element in self._window(hwnd).descendants():
            if element.is_visible() and needle == (element.element_info.name or "").casefold():
                try:
                    element.invoke()
                    return True
                except Exception:
                    return False
        return False

    def click_navigation_control(self, hwnd: int, name: str) -> str:
        needle = name.strip().casefold()
        allowed_types = {"Button", "MenuItem", "TabItem", "TreeItem"}
        matches = [
            element for element in self._window(hwnd).descendants()
            if element.is_visible()
            and element.element_info.control_type in allowed_types
            and (element.element_info.name or "").strip().casefold() == needle
        ]
        if len(matches) != 1:
            raise LookupError("No encontré un único control accesible con ese nombre.")
        element = matches[0]
        try:
            if element.element_info.control_type in {"TabItem", "TreeItem"}:
                element.select()
            else:
                element.invoke()
        except Exception as exc:
            raise RuntimeError("No pude activar ese control accesible.") from exc
        return element.element_info.name or name

    def invoke_save(self, hwnd: int) -> bool:
        # Prefer the application's named accessibility commands over keystrokes.
        if self.invoke_element(hwnd, "Guardar") or self.invoke_element(hwnd, "Save"):
            return True
        opened = self.invoke_element(hwnd, "Archivo") or self.invoke_element(hwnd, "File")
        if not opened:
            return False
        if self.invoke_element(hwnd, "Guardar") or self.invoke_element(hwnd, "Save"):
            return True
        # Close the menu before the keyboard fallback.
        from pywinauto.keyboard import send_keys
        send_keys("{ESC}")
        return False

    def selected_text(self) -> str:
        try:
            element = self._focused()
            text_pattern = element.iface_text
            if not text_pattern:
                raise LookupError("El control enfocado no expone texto seleccionado.")
            ranges = text_pattern.GetSelection()
            content = " ".join(r.GetText(-1) for r in ranges).strip()
            if not content:
                raise LookupError("No hay texto seleccionado.")
            return content[:600]
        except LookupError:
            raise
        except Exception as exc:
            raise RuntimeError("No pude leer el texto seleccionado.") from exc
