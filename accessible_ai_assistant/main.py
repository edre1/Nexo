"""Accessible Windows assistant entry point."""
import sys
from utils.error_reporting import install_exception_hooks

# Install before importing optional libraries so startup failures are retained too.
reporter = install_exception_hooks()
import ctypes
from hashlib import sha256
import tkinter as tk
import win32con
import win32event
import win32gui
import win32api
from winerror import ERROR_ALREADY_EXISTS

from actions.action_executor import ActionExecutor
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from config.settings import load_settings
from config.paths import RESOURCE_ROOT
from security.security_manager import SecurityManager
from speech.local_output import LocalSpeechOutput
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
    background = "--background" in sys.argv[1:]
    # Installed copies share an instance. Source checkouts can run independently.
    suffix = "installed" if getattr(sys, "frozen", False) else sha256(str(RESOURCE_ROOT).casefold().encode()).hexdigest()
    instance_name = rf"Local\Nexo-{suffix}"
    show_window = win32event.CreateEvent(None, False, False, instance_name + "-show")
    instance = win32event.CreateMutex(None, False, instance_name)
    try:
        if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
            if not background:
                win32event.SetEvent(show_window)
            return 0
        return run_app(background, show_window)
    finally:
        instance.Close()
        show_window.Close()


def run_app(background, show_window) -> int:
    # Keep window rectangles, screenshots and mouse coordinates in physical pixels.
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    logger = setup_logger()
    settings = load_settings()
    root = tk.Tk()
    if background:
        root.withdraw()
    root.update_idletasks()
    providers = {}
    if settings.api_key:
        providers["gemini"] = GeminiProvider(settings.api_key, settings.model)
    if settings.openai_api_key:
        providers["openai"] = OpenAIProvider(settings.openai_api_key, settings.openai_model)
    selected = settings.ai_provider if settings.ai_provider in providers else next(iter(providers), None)
    if selected is None:
        from tkinter import messagebox
        if not background:
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
    speech = LocalSpeechOutput(settings.speech_output)
    recognizer = ProviderSpeechRecognizer(provider)
    recognizer.engine = settings.speech_recognition
    MainWindow(root, settings, service, speech, recognizer, accessibility, logger, providers, selected, reporter=reporter)

    def check_show_window():
        if win32event.WaitForSingleObject(show_window, 0) == win32event.WAIT_OBJECT_0:
            root.deiconify()
            root.lift()
            root.focus_force()
        root.after(200, check_show_window)

    root.after(200, check_show_window)
    root.mainloop()
    if reporter:
        reporter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
