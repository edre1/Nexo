"""Keyboard navigable Tk interface. All Tk changes happen on the main thread."""
from queue import Empty, Queue
from dataclasses import replace
import threading
import webbrowser
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import win32con
import win32gui
import win32process
import pythoncom
from pydantic import ValidationError

from actions.action_registry import Level
from assistant_service import AssistantService, Prepared
from config.settings import Settings, save_listen_hotkey
from utils.connectivity import internet_available
from speech.local_models import download_models
from speech.output import WindowsSpeechOutput
from speech.recognizer import ProviderSpeechRecognizer, microphone_status
from updates import check_latest, release_settings
from windows.hotkeys import FUNCTION_KEYS, GlobalHotkeys
from windows.ui_automation import UIAutomation
from windows.computer_driver import ComputerDriver
from ai.computer_session import ComputerSession
from ai.advanced_session import AdvancedSession
from ai.openai_errors import credits_exhausted
from config.paths import RESOURCE_ROOT
from utils.advanced_activity import ACTIVITY_ROOT


class MainWindow:
    def __init__(self, root: tk.Tk, settings: Settings, service: AssistantService, speech: WindowsSpeechOutput, recognizer: ProviderSpeechRecognizer, accessibility: UIAutomation, logger, providers: dict, selected: str | None, reporter=None):
        self.root = root
        self.settings = settings
        self.service = service
        self.speech = speech
        self.recognizer = recognizer
        self.accessibility = accessibility
        self.logger = logger
        self.providers = providers
        self.selected = selected
        self.advanced_mode = selected == "openai" and settings.advanced_mode
        self.processing_timer = None
        self.review_dialog = None
        self.web_sources = []
        self.reporter = reporter
        self.online = None
        self.closed = threading.Event()
        self.messages = []
        self.message_index = -1
        self.events: Queue[tuple] = Queue()
        if "openai" in self.providers:
            self.providers["openai"].on_reasoning = lambda choice, phase: self.events.put(("reasoning", choice, phase))
        self.cancel_event = threading.Event()
        self.busy = False
        self.last_target = 0
        self.own_hwnd = win32gui.GetAncestor(root.winfo_id(), win32con.GA_ROOT)
        self._build()
        self.speech.on_error = lambda text: self.events.put(("voice_warning", text))
        self.hotkeys = GlobalHotkeys(settings.hotkey_listen, settings.hotkey_cancel, self._hotkey_event, provider=settings.hotkey_provider)
        try:
            self.hotkeys.start()
            self.status.set(f"Listo. Atajo para escuchar: {settings.hotkey_listen}.")
        except Exception as exc:
            self._announce_error(str(exc))
        self.root.after(100, self._drain)
        self.root.after(500, self._track_target)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.report_callback_exception = self._callback_error
        threading.Thread(target=self._monitor_connection, daemon=True).start()

    def _build(self):
        self.root.title("Nexo" if getattr(sys, "frozen", False) else "Nexo · Pruebas")
        icon = RESOURCE_ROOT / "assets" / "nexo.ico"
        if icon.is_file():
            self.root.iconbitmap(default=str(icon))
        self.root.geometry("820x760")
        self.root.minsize(520, 500)
        body = ttk.Frame(self.root, padding=16)
        body.pack(fill="both", expand=True)
        menu = tk.Menu(self.root)
        options = tk.Menu(menu, tearoff=False)
        options.add_command(label="Preferencias…", accelerator="Ctrl+,", command=self._settings_dialog)
        options.add_command(label="Buscar actualizaciones", command=self._check_updates)
        options.add_command(label="Reportes de errores…", command=self._reporting_dialog)
        options.add_command(label="Registro del modo avanzado…", command=self._open_advanced_activity)
        options.add_command(label="Fuentes de la última búsqueda…", command=self._open_web_sources)
        options.add_separator()
        options.add_command(label="Ocultar y seguir escuchando el atajo", command=self.root.withdraw)
        options.add_command(label="Salir de Nexo", command=self._close)
        menu.add_cascade(label="Configuración", underline=0, menu=options)
        self.root.config(menu=menu)
        ttk.Label(body, text="Nexo", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Iniciando asistente.")
        ttk.Label(body, text="Estado del asistente").pack(anchor="w")
        ttk.Label(body, textvariable=self.status, wraplength=620).pack(anchor="w", pady=(0, 10))
        self.connection_status = tk.StringVar(value="Comprobando conexión a internet…")
        ttk.Label(body, textvariable=self.connection_status).pack(anchor="w", pady=(0, 8))
        self.provider_status = tk.StringVar()
        ttk.Label(body, text="Estado del proveedor de inteligencia artificial").pack(anchor="w")
        ttk.Label(body, textvariable=self.provider_status, wraplength=620).pack(anchor="w", pady=(0, 8))
        self.reasoning_status = tk.StringVar(value="Luna: razonamiento automático. Alt+R lee el nivel elegido." if self.selected == "openai" else "Razonamiento automático de Nexo: disponible al seleccionar Luna.")
        ttk.Label(body, textvariable=self.reasoning_status, wraplength=740).pack(anchor="w", pady=(0, 8))
        self.provider_label = ttk.Label(body, text=f"Modelo para la siguiente petición · {self.settings.hotkey_provider} para cambiar")
        self.provider_label.pack(anchor="w")
        self.provider_choice = tk.StringVar()
        self.provider_combo = ttk.Combobox(body, textvariable=self.provider_choice, state="readonly", values=("Gemini", "GPT-6 Luna"))
        self.provider_combo.pack(fill="x", pady=(0, 10))
        self.provider_combo.current(0 if (self.selected or self.settings.ai_provider) == "gemini" else 1)
        self.provider_combo.bind("<<ComboboxSelected>>", self._select_provider)
        self._update_provider_status()
        self.mic_status = tk.StringVar(value=microphone_status())
        ttk.Label(body, text="Estado del micrófono").pack(anchor="w")
        ttk.Label(body, textvariable=self.mic_status, wraplength=620).pack(anchor="w", pady=(0, 10))
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(0, 10))
        self.listen_button = ttk.Button(buttons, text="Escuchar", command=self._start_voice)
        self.listen_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Detener o cancelar", command=self._cancel).pack(side="left")
        ttk.Button(buttons, text="Configuración", command=self._settings_dialog).pack(side="left", padx=(8, 0))
        ttk.Label(body, text="Conversación · Alt+H para leer; Alt+Arriba/Abajo recorre mensajes").pack(anchor="w")
        chat_frame = ttk.Frame(body)
        chat_frame.pack(fill="both", expand=True, pady=(6, 12))
        self.chat = tk.Text(chat_frame, state="disabled", wrap="word", font=("Segoe UI", 12), background="#f3f5fa", foreground="#172238", relief="flat", padx=16, pady=14, takefocus=True, height=10)
        scroll = ttk.Scrollbar(chat_frame, command=self.chat.yview)
        self.chat.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("user", background="#dce9ff", lmargin1=120, lmargin2=120, rmargin=16, spacing1=12, spacing3=12)
        self.chat.tag_configure("assistant", background="#ffffff", lmargin1=16, lmargin2=16, rmargin=100, spacing1=12, spacing3=12)
        self.chat.tag_configure("error", background="#ffe4e3", foreground="#851c16", lmargin1=16, lmargin2=16, rmargin=60, spacing1=12, spacing3=12)
        self.chat.bind("<KeyPress>", self._chat_key)
        self.chat.bind("<Tab>", lambda _e: self._focus_input())
        self.chat.bind("<Shift-Tab>", lambda _e: self._previous_focus())
        ttk.Label(body, text="Mensaje · Enter para enviar · Alt+M para escribir").pack(anchor="w")
        self.command_entry = ttk.Entry(body)
        self.command_entry.pack(fill="x", pady=(0, 5))
        self.command_entry.bind("<Return>", lambda _event: self._start_text())
        self.send_button = ttk.Button(body, text="Enviar mensaje", command=self._start_text)
        self.send_button.pack(anchor="e", pady=(0, 10))
        self._append_message("assistant", "Hola. Soy Nexo. Escribe un mensaje o usa el atajo de voz. Puedes revisar la conversación con Alt+H.")
        self._sync_controls()
        self.command_entry.focus_set()
        self.root.bind("<Escape>", lambda _event: self._cancel())
        self.root.bind("<Control-comma>", lambda _e: self._settings_dialog())
        self.root.bind("<Alt-m>", lambda _e: self._focus_input())
        self.root.bind("<Alt-h>", lambda _e: self.chat.focus_set())
        self.root.bind("<Alt-r>", lambda _e: self.speech.speak(self.reasoning_status.get()))
        self.root.bind("<Alt-Up>", lambda _e: self._read_message(-1))
        self.root.bind("<Alt-Down>", lambda _e: self._read_message(1))
        self.root.bind("<F6>", lambda _e: self._focus_input() if self.root.focus_get() == self.chat else self.chat.focus_set())

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _append_message(self, role, text):
        start = self.chat.index("end-1c")
        who = "Tú" if role == "user" else "Error" if role == "error" else "Nexo"
        self.chat.configure(state="normal")
        try:
            self.chat.insert("end", f"{who}\n{text}\n\n", role)
        finally:
            self.chat.configure(state="disabled")
        self.messages.append((start, f"{who}: {text}"))
        self.message_index = len(self.messages) - 1
        self.chat.see("end")

    def _chat_key(self, event):
        if event.state & 4 and event.keysym.lower() in {"c", "a"}:
            if event.keysym.lower() == "a":
                self.chat.tag_add("sel", "1.0", "end-1c")
                return "break"
            return None
        if event.keysym in {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Tab", "Escape", "F6"} or event.state & (8 | 0x20000) or (event.state & 4 and event.keysym == "comma"):
            return None
        return "break"

    def _focus_input(self):
        self.command_entry.focus_set()
        return "break"

    def _previous_focus(self):
        self.chat.tk_focusPrev().focus_set()
        return "break"

    def _read_message(self, direction):
        if self.messages:
            self.message_index = max(0, min(len(self.messages) - 1, self.message_index + direction))
            position, text = self.messages[self.message_index]
            self.chat.focus_set()
            self.chat.mark_set("insert", position)
            self.chat.see(position)
            self.speech.speak(text)
        return "break"

    def _announce_error(self, text, record=True):
        if record:
            self.logger.error("interface_error", exc_info=bool(sys.exc_info()[0]))
        self.status.set(text)
        self._append_message("error", text)
        self.speech.speak(text)

    def _callback_error(self, kind, exc, tb):
        self.logger.error("interface_callback_failed", exc_info=(kind, exc, tb))
        self._announce_error(self._friendly_error(exc), record=False)

    def _reporting_dialog(self):
        from ui.reporting_dialog import reporting_dialog
        from utils.error_reporting import get_reporter
        reporting_dialog(self.root, self.reporter or get_reporter(), lambda text, error=False: self.events.put(("diagnostics_notice", text, error)))

    def _open_advanced_activity(self):
        journal = ACTIVITY_ROOT / "actividad.txt"
        if journal.is_file():
            os.startfile(journal)
        else:
            self.speech.speak("Aún no hay actividad del modo avanzado.")

    def _open_web_sources(self):
        if not self.web_sources:
            self.speech.speak("Aún no hay fuentes de una búsqueda web.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Fuentes de la última búsqueda")
        dialog.transient(self.root)
        ttk.Label(dialog, text="Selecciona una fuente para abrirla en tu navegador.").pack(padx=16, pady=8)
        buttons = []
        for title, url in self.web_sources:
            button = ttk.Button(dialog, text=title[:90], command=lambda url=url: webbrowser.open(url))
            button.pack(fill="x", padx=16, pady=2)
            buttons.append(button)
        ttk.Button(dialog, text="Cerrar", command=dialog.destroy).pack(pady=8)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        buttons[0].focus_set()

    def _sync_controls(self):
        allowed = bool(self.online) and not self.busy
        self.listen_button.config(state="normal" if allowed else "disabled")
        self.send_button.config(state="normal" if allowed else "disabled")
        self.provider_combo.config(state="disabled" if self.busy else "readonly")

    def _monitor_connection(self):
        while not self.closed.is_set():
            connected = internet_available()
            if not self.closed.is_set():
                self.events.put(("connection", connected))
            self.closed.wait(5)

    def _apply_connection(self, connected):
        previous = self.online
        self.online = connected
        text = "Conectado a internet." if connected else "Sin conexión a internet. El envío y el micrófono están desactivados."
        self.connection_status.set(text)
        self._sync_controls()
        if previous != connected and (not connected or previous is False):
            self._append_message("assistant", text)
            self.speech.speak(text)
            if not connected:
                self.logger.error("connection_lost")
            elif self.reporter:
                self.reporter.retry_soon()

    def _can_send(self):
        if self.busy:
            return False
        if not self.online:
            self.speech.speak("Sin conexión a internet. No se puede enviar la petición." if self.online is False else "Espera mientras compruebo la conexión a internet.")
            return False
        if self.selected not in self.providers:
            self._announce_error("Falta configurar una clave API. Agrega una clave y reinicia Nexo.")
            return False
        return True

    def _settings_dialog(self):
        if self.busy:
            self.speech.speak("Espera a que termine la petición antes de cambiar la configuración.")
            return "break"
        dialog = tk.Toplevel(self.root)
        dialog.title("Configuración de Nexo")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Atajo para hablar: Ctrl+Alt más una letra o número.").pack(anchor="w")
        letters_and_digits = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        key = ttk.Combobox(frame, values=letters_and_digits, state="readonly", width=10)
        key.set(self.settings.hotkey_listen.split("+")[-1].upper())
        key.pack(anchor="w", pady=12)
        ttk.Label(frame, text="Atajo para cambiar de modelo: Ctrl+Alt más la tecla elegida.").pack(anchor="w")
        provider_key = ttk.Combobox(frame, values=(*FUNCTION_KEYS, *letters_and_digits), state="readonly", width=10)
        provider_key.set(self.settings.hotkey_provider.split("+")[-1].upper())
        provider_key.pack(anchor="w", pady=12)
        ttk.Label(frame, text="Reconocimiento: API del proveedor seleccionado.\nEscucha hasta 1 minuto; termina tras 3 segundos de silencio.").pack(anchor="w", pady=(4, 12))
        ttk.Label(frame, text="Voz para leer respuestas").pack(anchor="w")
        voice = ttk.Combobox(frame, state="readonly", values=("Piper · Claude high · español MX", "Voz de Windows"), width=34)
        voice.current(0 if self.settings.speech_output == "piper" else 1)
        voice.pack(anchor="w", pady=(4, 12))
        ttk.Label(frame, text="Descarga los modelos una vez con internet. Después el audio se procesa localmente.", wraplength=400).pack(anchor="w")
        ttk.Button(frame, text="Descargar modelos locales", command=self._download_models).pack(anchor="w", pady=10)
        confirm_actions = tk.BooleanVar(dialog, value=self.settings.require_confirmation_for_sensitive_actions)
        ttk.Checkbutton(frame, text="Pedir confirmación antes de ejecutar acciones", variable=confirm_actions).pack(anchor="w")
        ttk.Label(
            frame,
            text="Si desmarcas esta opción, Nexo ejecutará las acciones permitidas directamente. "
            "El control visual de Luna envía capturas de la ventana elegida a OpenAI.",
            wraplength=400,
        ).pack(anchor="w", pady=(4, 12))
        review = tk.BooleanVar(dialog, value=self.settings.review_transcript)
        ttk.Checkbutton(frame, text="Escuchar antes de enviar", variable=review).pack(anchor="w")
        advanced = tk.BooleanVar(dialog, value=self.settings.advanced_mode)
        advanced_option = ttk.Checkbutton(frame, text="Activar modo avanzado de Luna", variable=advanced)
        advanced_option.pack(anchor="w")
        if self.selected != "openai":
            advanced_option.state(["disabled"])
        ttk.Label(
            frame,
            text="Solo con Luna. Permite controlar el escritorio, acceder a archivos, usar internet y ejecutar PowerShell "
            "con los permisos de tu cuenta, sin las confirmaciones de Nexo. Puede enviar capturas y datos de la tarea a OpenAI. "
            "Nexo recuerda esta opción al reiniciar y solo la aplica con Luna.",
            wraplength=440,
        ).pack(anchor="w", pady=(4, 12))

        def save():
            if self.busy:
                self.speech.speak("Espera a que termine la petición antes de guardar la configuración.")
                return
            value = f"Ctrl+Alt+{key.get()}"
            provider_shortcut = f"Ctrl+Alt+{provider_key.get()}"
            selected_recognition = "provider"
            selected_voice = "piper" if voice.current() == 0 else "windows"
            selected_confirmation = confirm_actions.get()
            previous = self.settings
            provider_changed = provider_shortcut.upper() != previous.hotkey_provider.upper()
            candidate = None
            try:
                if provider_changed or value.upper() != previous.hotkey_listen.upper():
                    candidate = GlobalHotkeys(value, previous.hotkey_cancel, self._hotkey_event, provider=provider_shortcut)
                    self.hotkeys.close()
                    candidate.start(require_provider=provider_changed)
                save_listen_hotkey(
                    value, selected_recognition, selected_voice,
                    confirm_actions=selected_confirmation, hotkey_provider=provider_shortcut,
                    advanced_mode=advanced.get(), review_transcript=review.get(),
                )
            except Exception as exc:
                if candidate is not None:
                    candidate.close()
                    self.hotkeys = GlobalHotkeys(
                        previous.hotkey_listen, previous.hotkey_cancel, self._hotkey_event,
                        provider=previous.hotkey_provider,
                    )
                    try:
                        self.hotkeys.start()
                    except Exception as restore_error:
                        self._announce_error(str(restore_error))
                self._announce_error(f"No pude guardar la configuración. {self._friendly_error(exc)}")
                return
            if candidate is not None:
                self.hotkeys = candidate
                self.settings = replace(self.settings, hotkey_listen=value, hotkey_provider=provider_shortcut)
                self.provider_label.configure(text=f"Modelo para la siguiente petición · {provider_shortcut} para cambiar")
                self.status.set(f"Atajos guardados. Hablar: {value}. Cambiar modelo: {provider_shortcut}.")
            self._apply_preferences(selected_recognition, selected_voice, selected_confirmation)
            self.settings = replace(self.settings, advanced_mode=advanced.get(), review_transcript=review.get())
            enabled = self.selected == "openai" and self.settings.advanced_mode
            if enabled != self.advanced_mode:
                self.advanced_mode = enabled
                self._update_provider_status()
                self.speech.speak("Modo avanzado de Luna activado." if enabled else "Modo avanzado de Luna desactivado.")
            if candidate is not None:
                self.speech.speak(self.status.get())
            dialog.destroy()
        ttk.Button(frame, text="Guardar", command=save).pack(side="left", padx=(0, 10))
        ttk.Button(frame, text="Cancelar", command=dialog.destroy).pack(side="left")
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.bind("<Return>", lambda _e: save())
        key.focus_set()
        self.root.wait_window(dialog)
        self.command_entry.focus_set()
        return "break"

    def _apply_preferences(self, recognition, voice, confirm_actions):
        self.settings = replace(
            self.settings, speech_recognition=recognition, speech_output=voice,
            require_confirmation_for_sensitive_actions=confirm_actions,
        )
        self.service.security.require_confirmation = confirm_actions
        self.recognizer.engine = recognition
        self.speech.engine = voice
        status = "activada" if confirm_actions else "desactivada"
        self.speech.speak(f"Configuración guardada. Confirmación de acciones {status}.")

    def _download_models(self):
        if getattr(self, "downloading_models", False):
            return
        self.downloading_models = True
        self.status.set("Preparando descarga de modelos locales.")
        self.speech.speak("Descargando los modelos locales. Puede tardar varios minutos.")
        def work():
            try:
                download_models(lambda text: self.events.put(("status", text)))
                self.events.put(("models_ready",))
            except Exception:
                self.logger.error("model_download_failed", exc_info=True)
                self.events.put(("models_error",))
        threading.Thread(target=work, daemon=True).start()

    def _target(self) -> int:
        active = win32gui.GetForegroundWindow()
        if active and win32process.GetWindowThreadProcessId(active)[1] != os.getpid():
            self.last_target = active
        return self.last_target

    def _check_updates(self):
        if not self._can_send():
            return
        self.status.set("Buscando actualizaciones en GitHub.")
        def work():
            try:
                self.events.put(("update", check_latest()))
            except Exception as exc:
                self.logger.error("update_check_failed", exc_info=True)
                self.events.put(("update_error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _update_provider_status(self):
        name = "Gemini" if self.selected == "gemini" else "GPT-6 Luna" if self.selected == "openai" else "Ninguno"
        self.provider_status.set(
            f"Activo: {name}. Gemini: {'configurado' if 'gemini' in self.providers else 'sin clave'}. "
            f"GPT-6 Luna: {'configurado · control visual disponible' if 'openai' in self.providers else 'sin clave'}."
            + (" Modo avanzado activado." if self.advanced_mode else "")
        )

    def _select_provider(self, _event=None):
        self._set_provider("openai" if self.provider_combo.current() == 1 else "gemini")

    def _set_provider(self, requested, *, announce=True):
        active_index = 1 if (self.selected or self.settings.ai_provider) == "openai" else 0
        if self.busy:
            self.provider_combo.current(active_index)
            self.speech.speak("Espera a que termine la petición para cambiar de modelo.")
            return
        if requested not in self.providers:
            self.provider_combo.current(active_index)
            self._announce_error(f"Falta la clave de {'OpenAI' if requested == 'openai' else 'Gemini'}. Agrégala en .env y reinicia.")
            return
        self.selected = requested
        advanced_disabled = requested == "gemini" and self.advanced_mode
        self.advanced_mode = requested == "openai" and self.settings.advanced_mode
        provider = self.providers[requested]
        self.service.provider = provider
        self.service.executor.provider = provider
        self.recognizer.provider = provider
        self._update_provider_status()
        self.reasoning_status.set("Luna: razonamiento automático; se elegirá al enviar la petición." if requested == "openai" else "Razonamiento automático de Nexo: disponible al seleccionar Luna.")
        self.provider_combo.current(1 if requested == "openai" else 0)
        announcement = "Luna. Configurado para peticiones complejas." if requested == "openai" else "Gemini. Configurado para preguntas sencillas."
        if advanced_disabled:
            announcement += " Modo avanzado de Luna desactivado."
        elif self.advanced_mode:
            announcement += " Modo avanzado de Luna activado."
        if announce:
            self.status.set(announcement)
            self.speech.speak(announcement)

    def _track_target(self):
        self._target()
        self.root.after(500, self._track_target)

    def _hotkey_event(self, event: str):
        if event in {"switch_provider", "provider_hotkey_unavailable"}:
            self.events.put((event,))
            return
        if event == "cancel":
            self.cancel_event.set()
        target = self._target()
        self.events.put((event, target))

    def _start_voice(self, target: int | None = None):
        if not self._can_send():
            return
        target = self._target() if target is None else target
        self.busy = True
        self.cancel_event.clear()
        self.status.set("Preparando micrófono.")
        self._sync_controls()
        threading.Thread(target=self._worker, args=(None, target), daemon=True).start()

    def _start_text(self):
        if not self._can_send():
            return
        utterance = self.command_entry.get().strip()
        if not utterance:
            self._announce_error("Escribe una petición primero.")
            return
        target = self._target()
        self.busy = True
        self.cancel_event.clear()
        self._sync_controls()
        threading.Thread(target=self._worker, args=(utterance, target), daemon=True).start()

    def _worker(self, utterance: str | None, target: int, replay=False):
        pythoncom.CoInitialize()
        pending_confirmation = False
        can_replay = False
        try:
            if not internet_available():
                self.events.put(("connection", False))
                self.events.put(("done",))
                return
            if utterance is None:
                def ready():
                    self.speech.speak_and_wait("Habla ahora")
                    self.events.put(("status", "Habla ahora. Hasta 1 minuto o 3 segundos de silencio."))
                utterance = self.recognizer.listen(
                    self.cancel_event, self.settings.microphone_max_seconds, self.settings.language,
                    on_ready=ready, on_recorded=lambda: self.events.put(("recorded",)),
                )
                if self.settings.review_transcript and not self.cancel_event.is_set():
                    answer = []
                    decided = threading.Event()
                    self.events.put(("review", utterance, answer, decided))
                    self.speech.speak_and_wait(
                        f"Entendí lo siguiente. {utterance} "
                        "Pulsa Enter para enviar, otra tecla para repetir o Escape para cancelar. "
                        "Si esperas tres segundos, lo enviaré."
                    )
                    self.events.put(("review_read", decided))
                    while not decided.wait(0.1):
                        if self.cancel_event.is_set():
                            return
                    if answer[0] == "retry":
                        self.events.put(("retry_voice", target))
                        return
                    if answer[0] != "send":
                        return
                    if not internet_available():
                        self.events.put(("connection", False))
                        self.events.put(("done",))
                        return
            if self.cancel_event.is_set():
                return
            if not replay:
                self.events.put(("transcript", utterance))
            self.events.put(("processing",))
            self.events.put(("status", f"Consultando {'GPT-6 Luna' if self.selected == 'openai' else 'Gemini'}."))
            try:
                title = win32gui.GetWindowText(target) if target and win32gui.IsWindow(target) else ""
                context = f"Ventana de destino: {title or 'no identificada'}"
            except Exception:
                self.logger.warning("target_context_unavailable", exc_info=True)
                context = "Ventana de destino no identificada"
            if self.selected == "openai" and self.advanced_mode:
                driver = ComputerDriver(target, self.own_hwnd, self.cancel_event, desktop=True)
                session = AdvancedSession(self.service.provider, driver, self.cancel_event, lambda text: self.events.put(("status", text)))
                recent = "\n".join(f"Usuario: {u}\nNexo: {a}" for u, a in self.service.history[-3:])
                result = session.run(utterance, recent, context)
                if not self.cancel_event.is_set():
                    self.service.history = (self.service.history + [(utterance, result)])[-3:]
                    self.events.put(("advanced_result", result, session.sources))
                return
            try:
                focus = self.accessibility.focused_element() if target else ""
            except Exception:
                self.logger.warning("focus_unavailable", exc_info=True)
                focus = ""
            can_replay = True
            prepared = self.service.prepare(utterance, context, target, focus)
            can_replay = False
            if self.cancel_event.is_set():
                return
            if prepared.decision and prepared.decision.level == Level.CONFIRM:
                pending_confirmation = True
                self.events.put(("confirm", prepared, utterance))
            else:
                self._execute(prepared, utterance)
        except InterruptedError:
            self.events.put(("status", "Escucha cancelada."))
        except Exception as exc:
            self.logger.error("request_failed", exc_info=True)
            if self.selected == "openai" and credits_exhausted(exc):
                self.events.put(("credits_exhausted", utterance if can_replay else None, target, utterance is None))
            else:
                self.events.put(("error", self._friendly_error(exc)))
        finally:
            pythoncom.CoUninitialize()
            if self.cancel_event.is_set() and not pending_confirmation:
                self.events.put(("done",))

    def _start_processing_timer(self):
        if self.processing_timer is None and not self.cancel_event.is_set():
            def announce():
                self.processing_timer = None
                if self.busy and not self.cancel_event.is_set():
                    self.speech.speak("Procesando.")
            self.processing_timer = self.root.after(1800, announce)

    def _stop_processing_timer(self):
        if self.processing_timer is not None:
            self.root.after_cancel(self.processing_timer)
            self.processing_timer = None

    def _review_voice(self, utterance, answer, decided):
        self._stop_processing_timer()
        dialog = tk.Toplevel(self.root)
        self.review_dialog = dialog
        self.review_decided = decided
        self.review_timer = None
        dialog.title("Revisar transcripción")
        ttk.Label(dialog, text=utterance, wraplength=480).pack(padx=16, pady=12)
        ttk.Label(dialog, text="Enter para enviar. Escape para cancelar. Otra tecla para repetir.").pack(padx=16, pady=(0, 12))

        def finish(choice):
            if self.review_dialog is not dialog:
                return "break"
            if self.review_timer is not None:
                self.root.after_cancel(self.review_timer)
            self.review_dialog = None
            dialog.destroy()
            answer.append(choice)
            if choice == "cancel":
                self.cancel_event.set()
                self.status.set("Dictado cancelado.")
            decided.set()
            return "break"

        self.review_finish = finish
        def key_pressed(event):
            if event.keysym in {"Escape", "Return", "KP_Enter"}:
                return finish("cancel" if event.keysym == "Escape" else "send")
            if event.keysym not in {"Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R", "Win_L", "Win_R"}:
                return finish("retry")
            return "break"

        dialog.bind("<KeyPress>", key_pressed)
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish("cancel"))
        dialog.lift()
        dialog.grab_set()
        dialog.focus_force()
        self.status.set("Revisando la transcripción.")

    def _execute(self, prepared: Prepared, utterance: str):
        try:
            if self.cancel_event.is_set():
                self.events.put(("done",))
                return
            if prepared.decision and prepared.decision.level == Level.BLOCKED:
                result = self.service.execute(prepared, utterance)
            elif prepared.reply.action == "computer_control":
                if self.selected != "openai":
                    raise ValueError("El control visual está disponible al seleccionar GPT-6 Luna.")
                if not self.settings.enable_screen_vision:
                    raise ValueError("Activa la visión de pantalla para usar el control visual.")
                driver = ComputerDriver(prepared.target_hwnd, self.own_hwnd, self.cancel_event)
                confirm = self._confirm_visual if self.settings.require_confirmation_for_sensitive_actions else None
                session = ComputerSession(self.service.provider, driver, self.cancel_event, confirm, lambda text: self.events.put(("status", text)))
                recent = "\n".join(f"Usuario: {u}\nNexo: {a}" for u, a in self.service.history[-3:])
                result = session.run(utterance, recent)
                self.service.history.append((utterance, result))
                self.service.history = self.service.history[-3:]
            else:
                result = self.service.execute(prepared, utterance)
            if not self.cancel_event.is_set():
                self.events.put(("result", result, prepared.reply.action or "respuesta"))
        except InterruptedError:
            self.events.put(("result", "Control visual cancelado.", "cancelada"))
        except Exception as exc:
            self.logger.error("action_failed", exc_info=True)
            if self.selected == "openai" and credits_exhausted(exc):
                retry = utterance if prepared.reply.action == "get_screen_description" else None
                self.events.put(("credits_exhausted", retry, prepared.target_hwnd, False))
            else:
                self.events.put(("error", self._friendly_error(exc)))

    def _handle_credits_exhausted(self, utterance, target, dictation_failed):
        if self.cancel_event.is_set():
            return
        message = "Se agotaron los créditos de OpenAI."
        if "gemini" not in self.providers:
            self._finish(message + " Configura la clave de Gemini para seguir usando Nexo.", "error")
            return
        self.busy = False
        self._set_provider("gemini", announce=False)
        message += " Cambié a Gemini."
        if utterance is None:
            detail = " Vuelve a dictar tu petición." if dictation_failed else " La petición anterior se detuvo. Puedes hacer una nueva petición."
            self._finish(message + detail, "error")
            return
        self._stop_processing_timer()
        self.status.set(message)
        self._append_message("assistant", message)
        self.speech.speak(message)
        self.busy = True
        self._sync_controls()
        threading.Thread(target=self._worker, args=(utterance, target, True), daemon=True).start()

    def _confirm_visual(self, text):
        answer = {"accepted": False}
        ready = threading.Event()
        self.events.put(("visual_confirm", text, answer, ready))
        while not ready.wait(0.1):
            if self.cancel_event.is_set() or self.closed.is_set():
                return False
        return answer["accepted"] and not self.cancel_event.is_set()

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "La IA devolvió una respuesta incompleta o con un formato que no pude interpretar. Intenta pedirlo de nuevo."
        message = str(exc)
        if isinstance(exc, (RuntimeError, LookupError, FileNotFoundError, ValueError)) and message:
            return message[:250]
        if "429" in message or "RESOURCE_EXHAUSTED" in message:
            return "Se alcanzó el límite del proveedor. Espera un momento e inténtalo de nuevo."
        if "503" in message or "UNAVAILABLE" in message:
            return "El proveedor está ocupado en este momento. Inténtalo de nuevo en unos minutos."
        if "API_KEY" in message or "403" in message or "401" in message:
            return "La clave del proveedor seleccionado no funciona o no tiene acceso a este modelo."
        return "No pude completar la acción. Revisa la conexión o inténtalo de nuevo."

    def _drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "listen":
                    if self.review_dialog is not None:
                        self.review_finish("retry")
                    else:
                        self._start_voice(event[1])
                elif kind == "switch_provider":
                    self._set_provider("gemini" if self.selected == "openai" else "openai")
                elif kind == "provider_hotkey_unavailable":
                    self._announce_error(f"El atajo {self.settings.hotkey_provider} no está disponible. Puedes elegir otro en Preferencias.")
                elif kind == "cancel":
                    self._cancel()
                elif kind == "status":
                    self.status.set(event[1])
                elif kind == "diagnostics_notice":
                    if event[2]:
                        self._announce_error(event[1])
                    else:
                        self.status.set(event[1])
                        self.speech.speak(event[1])
                elif kind == "connection":
                    self._apply_connection(event[1])
                elif kind == "reasoning":
                    choice, phase = event[1:]
                    phases = {"interpret": "interpretar la petición", "vision": "analizar la pantalla", "computer": "controlar la ventana", "advanced": "trabajar en modo avanzado"}
                    self.reasoning_status.set(f"Luna · razonamiento {choice.label} para {phases[phase]}: {choice.reason}.")
                elif kind == "voice_warning":
                    self.status.set(event[1])
                    self._append_message("error", event[1])
                elif kind == "models_ready":
                    self.downloading_models = False
                    self.speech.engine = self.settings.speech_output
                    self.status.set("Piper listo para usar.")
                    self.speech.speak("Piper está listo para usar.")
                elif kind == "models_error":
                    self.downloading_models = False
                    self._announce_error("No pude descargar los modelos. Revisa internet y el espacio disponible e inténtalo de nuevo.")
                elif kind == "update":
                    if event[1] is None:
                        self.status.set(f"La versión {release_settings()['version']} está actualizada.")
                    else:
                        version, page = event[1]
                        self.status.set(f"Actualización {version} disponible.")
                        if not self.settings.require_confirmation_for_sensitive_actions or messagebox.askyesno("Actualización disponible", f"Hay una versión {version}. ¿Quieres abrir la página de descarga en GitHub?", parent=self.root):
                            webbrowser.open(page)
                elif kind == "update_error":
                    self._announce_error(f"No pude buscar actualizaciones: {event[1][:180]}")
                elif kind == "recorded":
                    if not self.cancel_event.is_set():
                        self.status.set("Escucha terminada. Transcribiendo.")
                        self.speech.speak("Terminé de escuchar.")
                        self._start_processing_timer()
                elif kind == "processing":
                    self._stop_processing_timer()
                    self._start_processing_timer()
                elif kind == "review":
                    if not self.cancel_event.is_set():
                        self._review_voice(*event[1:])
                elif kind == "review_read":
                    if self.review_dialog is not None and self.review_decided is event[1] and not self.cancel_event.is_set():
                        self.review_timer = self.root.after(3000, lambda: self.review_finish("send"))
                elif kind == "retry_voice":
                    self.busy = False
                    self._sync_controls()
                    if not self.cancel_event.is_set():
                        self._start_voice(event[1])
                elif kind == "transcript":
                    self._append_message("user", event[1])
                    self.command_entry.delete(0, "end")
                elif kind == "visual_confirm":
                    self._stop_processing_timer()
                    text, answer, ready = event[1:]
                    try:
                        if not self.cancel_event.is_set():
                            self.speech.speak(text)
                            answer["accepted"] = messagebox.askyesno("Confirmar control visual de Luna", text, parent=self.root)
                    finally:
                        ready.set()
                    if answer["accepted"]:
                        self._start_processing_timer()
                elif kind == "confirm":
                    self._stop_processing_timer()
                    prepared, utterance = event[1], event[2]
                    if self.cancel_event.is_set():
                        self._finish("Acción cancelada.", "cancelada")
                        continue
                    action = prepared.reply.action
                    detail = prepared.reply.parameters.get("text", "")[:120] if action == "write_text" else ""
                    if action == "computer_control":
                        prompt = "¿Permites a Luna iniciar el control visual de la ventana elegida? Se enviarán capturas de esa ventana a OpenAI. Confirmarás los clics, la escritura y las teclas antes de ejecutarlos. Para detenerlo usa el atajo de cancelar."
                    elif action == "click_control":
                        prompt = f"¿Confirmas activar el control {prepared.reply.parameters['name']} en la ventana de destino?"
                    elif action == "close_application":
                        prompt = "¿Confirmas cerrar la ventana de destino? Podría haber cambios sin guardar."
                    else:
                        prompt = f"La acción {action} puede cambiar contenido. ¿Confirmas?"
                    if detail:
                        prompt += f"\n\nTexto: {detail}"
                    self.speech.speak(prompt)
                    if messagebox.askyesno("Confirmar acción", prompt, parent=self.root):
                        self._start_processing_timer()
                        threading.Thread(target=self._confirmed_worker, args=(prepared, utterance), daemon=True).start()
                    else:
                        self._finish("Acción cancelada.", "cancelada")
                elif kind == "result":
                    self._finish(event[1], event[2])
                elif kind == "advanced_result":
                    text, sources = event[1:]
                    if sources:
                        self.web_sources = sources
                        text += " Puedes abrir las fuentes desde el menú Configuración."
                    self._finish(text, "modo avanzado")
                elif kind == "credits_exhausted":
                    self._handle_credits_exhausted(*event[1:])
                elif kind == "error":
                    if self.review_dialog is not None:
                        self.review_finish("error")
                    if self.cancel_event.is_set():
                        self.status.set("Acción cancelada.")
                    else:
                        self._finish(event[1], "error")
                elif kind == "done":
                    self._stop_processing_timer()
                    self.busy = False
                    self._sync_controls()
                    if self.cancel_event.is_set():
                        self.status.set("Acción cancelada.")
        except Empty:
            pass
        self.root.after(100, self._drain)

    def _confirmed_worker(self, prepared: Prepared, utterance: str):
        pythoncom.CoInitialize()
        try:
            self._execute(prepared, utterance)
        finally:
            pythoncom.CoUninitialize()
            if self.cancel_event.is_set():
                self.events.put(("done",))

    def _finish(self, result: str, label: str):
        self._stop_processing_timer()
        self.status.set(result if label == "error" else "Listo.")
        self._append_message("error" if label == "error" else "assistant", result)
        self.speech.speak(result)
        self.busy = False
        self._sync_controls()

    def _cancel(self):
        self.cancel_event.set()
        self._stop_processing_timer()
        if self.review_dialog is not None:
            self.review_finish("cancel")
        self.status.set("Cancelando; espera a que termine la petición en curso.")

    def _close(self):
        self.closed.set()
        self.cancel_event.set()
        self.hotkeys.close()
        self.speech.close()
        if self.reporter:
            self.reporter.close()
        self.root.destroy()
