"""Accessible Windows assistant entry point."""
import sys
import tkinter as tk
import win32con
import win32gui

from actions.action_executor import ActionExecutor
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from config.settings import load_settings
from security.security_manager import SecurityManager
from speech.output import WindowsSpeechOutput
from speech.recognizer import ProviderSpeechRecognizer
from ui.main_window import MainWindow
from utils.logger import setup_logger
from windows.ui_automation import UIAutomation
from windows.windows_controller import WindowsController
from assistant_service import AssistantService


def main() -> int:
    if sys.platform != "win32":
        print("Esta primera versión requiere Windows.")
        return 1
    settings = load_settings()
    logger = setup_logger()
    root = tk.Tk()
    root.update_idletasks()
    providers = {}
    if settings.api_key:
        providers["gemini"] = GeminiProvider(settings.api_key, settings.model)
    if settings.openai_api_key:
        providers["openai"] = OpenAIProvider(settings.openai_api_key, settings.openai_model)
    selected = settings.ai_provider if settings.ai_provider in providers else next(iter(providers), None)
    if selected is None:
        from tkinter import messagebox
        root.after(200, lambda: messagebox.showwarning(
            "Configurar clave API", "Falta una clave API. Agrega GEMINI_API_KEY u OPENAI_API_KEY en .env y reinicia la aplicación.", parent=root
        ))
        class MissingProvider:
            def __getattr__(self, _name):
                raise ValueError("Falta configurar una clave API. Consulta README.md.")
        provider = MissingProvider()
    else:
        provider = providers[selected]
    accessibility = UIAutomation()
    controller = WindowsController(win32gui.GetAncestor(root.winfo_id(), win32con.GA_ROOT))
    executor = ActionExecutor(controller, accessibility, provider, settings.enable_screen_vision)
    service = AssistantService(provider, SecurityManager(settings.require_confirmation_for_sensitive_actions), executor, logger, settings.learning_mode)
    speech = WindowsSpeechOutput()
    recognizer = ProviderSpeechRecognizer(provider)
    MainWindow(root, settings, service, speech, recognizer, accessibility, logger, providers, selected)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
