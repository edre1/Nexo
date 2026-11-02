"""Dispatch validated actions to fixed Windows capabilities."""
import win32gui
from actions.action_models import AIReply
from ai.base_provider import AIProvider
from windows.screen_capture import capture_screen
from windows.ui_automation import UIAutomation
from windows.windows_controller import WindowsController


class ActionExecutor:
    def __init__(self, controller: WindowsController, accessibility: UIAutomation, provider: AIProvider, enable_vision: bool):
        self.controller = controller
        self.accessibility = accessibility
        self.provider = provider
        self.enable_vision = enable_vision

    def execute(self, reply: AIReply, target_hwnd: int, question: str = "") -> str:
        action = reply.action
        args = reply.parameters
        if action == "open_application":
            return self.controller.open_application(args["application"])
        if action == "close_application":
            return self.controller.close_application(target_hwnd)
        if action == "get_active_window":
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == self.controller.own_hwnd and target_hwnd:
                hwnd = target_hwnd
            title = win32gui.GetWindowText(hwnd).strip() if hwnd else ""
            return f"Estás en {title}." if title else "No encontré una ventana con título."
        if action == "list_visible_controls":
            title = win32gui.GetWindowText(target_hwnd) or "esta ventana"
            controls = self.accessibility.visible_controls(target_hwnd)
            if not controls:
                return f"Estás en {title}. No encontré controles accesibles visibles."
            return f"En {title} encontré: " + "; ".join(controls[:20]) + "."
        if action == "focus_control":
            name = self.accessibility.focus_element(target_hwnd, args["name"])
            return f"Foco colocado en {name}."
        if action == "move_cursor":
            return self.controller.move_cursor(target_hwnd, args["direction"].strip().lower(), int(args.get("count", "1")))
        if action == "click_control":
            self.controller.activate_target(target_hwnd)
            name = self.accessibility.click_navigation_control(target_hwnd, args["name"])
            return f"Activé el control {name}."
        if action == "write_text":
            return self.controller.write_text(target_hwnd, args["text"])
        if action == "press_key":
            if args["key"].upper().replace("CONTROL", "CTRL").replace(" ", "") == "CTRL+S":
                return self._save_file(target_hwnd)
            return self.controller.press_key(target_hwnd, args["key"])
        if action == "save_file":
            return self._save_file(target_hwnd)
        if action == "get_current_focus":
            self.controller.activate_target(target_hwnd)
            return "El foco está en " + self.accessibility.focused_element() + "."
        if action == "read_selected_text":
            self.controller.activate_target(target_hwnd)
            return "Texto seleccionado: " + self.accessibility.selected_text()
        if action == "get_screen_description":
            title = win32gui.GetWindowText(target_hwnd) or "ventana sin título"
            try:
                controls = self.accessibility.visible_controls(target_hwnd, limit=20)
                focus = self.accessibility.focused_element()
                context = f"Ventana: {title}. Foco: {focus}. Controles: " + "; ".join(controls)
            except Exception:
                context = f"Ventana: {title}."
            if not self.enable_vision:
                return context
            try:
                return self.provider.describe_image(capture_screen(), context, question)
            except Exception:
                return context + " No pude analizar la captura visual."
        if action in {"volume_up", "volume_down", "mute_volume"}:
            return self.controller.volume(action)
        raise RuntimeError("Acción desconocida bloqueada.")

    def _save_file(self, target_hwnd: int) -> str:
        self.controller.activate_target(target_hwnd)
        if self.accessibility.invoke_save(target_hwnd):
            return "Envié Guardar mediante el control accesible. Si apareció un diálogo, completa el nombre y la ubicación con el teclado."
        return self.controller.save_file(target_hwnd)
