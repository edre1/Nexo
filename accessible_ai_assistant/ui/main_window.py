"""Keyboard navigable Tk interface. All Tk changes happen on the main thread."""
from queue import Empty, Queue
from dataclasses import replace
import threading
import webbrowser
import os
import tkinter as tk
from tkinter import messagebox, ttk
import win32con
import win32gui
import win32process
import pythoncom

from actions.action_registry import Level
from assistant_service import AssistantService, Prepared
from config.settings import Settings, save_listen_hotkey
from utils.connectivity import internet_available
from speech.output import WindowsSpeechOutput
from speech.recognizer import ProviderSpeechRecognizer, microphone_status
from updates import check_latest, release_settings
from windows.hotkeys import GlobalHotkeys
from windows.ui_automation import UIAutomation


class MainWindow:
    def __init__(self, root: tk.Tk, settings: Settings, service: AssistantService, speech: WindowsSpeechOutput, recognizer: ProviderSpeechRecognizer, accessibility: UIAutomation, logger, providers: dict, selected: str | None):
        self.root = root
        self.settings = settings
        self.service = service
        self.speech = speech
        self.recognizer = recognizer
        self.accessibility = accessibility
        self.logger = logger
        self.providers = providers
        self.selected = selected
        self.online = None
        self.closed = threading.Event()
        self.messages = []
        self.message_index = -1
        self.events: Queue[tuple] = Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.last_target = 0
        self.own_hwnd = win32gui.GetAncestor(root.winfo_id(), win32con.GA_ROOT)
        self._build()
        self.hotkeys = GlobalHotkeys(settings.hotkey_listen, settings.hotkey_cancel, self._hotkey_event)
        try:
            self.hotkeys.start()
            self.status.set(f"Listo. Atajo para escuchar: {settings.hotkey_listen}.")
        except Exception as exc:
            self._announce_error(str(exc))
            self.logger.error("Fallo de atajo global: %s", type(exc).__name__)
        self.root.after(100, self._drain)
        self.root.after(500, self._track_target)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.report_callback_exception = lambda _kind, exc, _tb: self._announce_error(self._friendly_error(exc))
        threading.Thread(target=self._monitor_connection, daemon=True).start()

    def _build(self):
        self.root.title("Nexo · Pruebas")
        self.root.geometry("820x760")
        self.root.minsize(520, 500)
        body = ttk.Frame(self.root, padding=16)
        body.pack(fill="both", expand=True)
        menu = tk.Menu(self.root)
        options = tk.Menu(menu, tearoff=False)
        options.add_command(label="Configurar atajo…", accelerator="Ctrl+,", command=self._settings_dialog)
        options.add_command(label="Buscar actualizaciones", command=self._check_updates)
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
        ttk.Label(body, text="Modelo para la siguiente petición").pack(anchor="w")
        self.provider_choice = tk.StringVar(value=self.selected or "gemini")
        self.provider_combo = ttk.Combobox(body, textvariable=self.provider_choice, state="readonly", values=("Gemini", "GPT-6 Luna"))
        self.provider_combo.pack(fill="x", pady=(0, 10))
        self.provider_combo.current(0 if self.selected != "openai" else 1)
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
        self.chat = tk.Text(chat_frame, wrap="word", font=("Segoe UI", 12), background="#f3f5fa", foreground="#172238", relief="flat", padx=16, pady=14, takefocus=True, height=10)
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
        self.chat.insert("end", f"{who}\n{text}\n\n", role)
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

    def _announce_error(self, text):
        self.status.set(text)
        self._append_message("error", text)
        self.speech.speak(text)

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
            self.speech.speak("Espera a que termine la petición antes de cambiar el atajo.")
            return "break"
        dialog = tk.Toplevel(self.root)
        dialog.title("Configuración de Nexo")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Atajo para hablar: Ctrl+Alt más una letra o número.").pack(anchor="w")
        key = ttk.Combobox(frame, values=tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"), state="readonly", width=10)
        key.set(self.settings.hotkey_listen.split("+")[-1].upper())
        key.pack(anchor="w", pady=12)
        def save():
            value = f"Ctrl+Alt+{key.get()}"
            old = self.settings.hotkey_listen
            if value.upper() == old.upper():
                dialog.destroy()
                return
            self.hotkeys.close()
            candidate = GlobalHotkeys(value, self.settings.hotkey_cancel, self._hotkey_event)
            try:
                candidate.start()
                save_listen_hotkey(value)
            except Exception as exc:
                candidate.close()
                self.hotkeys = GlobalHotkeys(old, self.settings.hotkey_cancel, self._hotkey_event)
                try:
                    self.hotkeys.start()
                except Exception as restore_error:
                    self._announce_error(str(restore_error))
                self._announce_error(f"No pude cambiar el atajo. {self._friendly_error(exc)}")
                return
            self.hotkeys = candidate
            self.settings = replace(self.settings, hotkey_listen=value)
            self.status.set(f"Atajo para hablar: {value}.")
            self.speech.speak(f"Atajo guardado: {value}.")
            dialog.destroy()
        ttk.Button(frame, text="Guardar", command=save).pack(side="left", padx=(0, 10))
        ttk.Button(frame, text="Cancelar", command=dialog.destroy).pack(side="left")
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.bind("<Return>", lambda _e: save())
        key.focus_set()
        self.root.wait_window(dialog)
        self.command_entry.focus_set()
        return "break"

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
                self.events.put(("update_error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _update_provider_status(self):
        name = "Gemini" if self.selected == "gemini" else "GPT-6 Luna" if self.selected == "openai" else "Ninguno"
        self.provider_status.set(
            f"Activo: {name}. Gemini: {'configurado' if 'gemini' in self.providers else 'sin clave'}. "
            f"GPT-6 Luna: {'configurado' if 'openai' in self.providers else 'sin clave'}."
        )

    def _select_provider(self, _event=None):
        requested = "openai" if self.provider_combo.current() == 1 else "gemini"
        if self.busy:
            self.provider_combo.current(0 if self.selected != "openai" else 1)
            return
        if requested not in self.providers:
            self.provider_combo.current(0 if self.selected != "openai" else 1)
            self._announce_error(f"Falta la clave de {'OpenAI' if requested == 'openai' else 'Gemini'}. Agrégala en .env y reinicia.")
            return
        self.selected = requested
        provider = self.providers[requested]
        self.service.provider = provider
        self.service.executor.provider = provider
        self.recognizer.provider = provider
        self._update_provider_status()
        self.status.set(f"Modelo seleccionado: {'GPT-6 Luna' if requested == 'openai' else 'Gemini'}.")

    def _track_target(self):
        self._target()
        self.root.after(500, self._track_target)

    def _hotkey_event(self, event: str):
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

    def _worker(self, utterance: str | None, target: int):
        pythoncom.CoInitialize()
        pending_confirmation = False
        try:
            if not internet_available():
                self.events.put(("connection", False))
                self.events.put(("done",))
                return
            if utterance is None:
                self.speech.speak_and_wait("Asistente listo.")
                self.events.put(("status", "Escuchando. Habla ahora."))
                utterance = self.recognizer.listen(self.cancel_event, self.settings.microphone_max_seconds, self.settings.language)
            if self.cancel_event.is_set():
                return
            self.events.put(("transcript", utterance))
            self.events.put(("status", f"Consultando {'GPT-6 Luna' if self.selected == 'openai' else 'Gemini'}."))
            try:
                title = win32gui.GetWindowText(target) if target and win32gui.IsWindow(target) else ""
                context = f"Ventana de destino: {title or 'no identificada'}"
            except Exception:
                context = "Ventana de destino no identificada"
            try:
                focus = self.accessibility.focused_element() if target else ""
            except Exception:
                focus = ""
            prepared = self.service.prepare(utterance, context, target, focus)
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
            self.logger.error("Error en flujo: %s", type(exc).__name__)
            self.events.put(("error", self._friendly_error(exc)))
        finally:
            pythoncom.CoUninitialize()
            if self.cancel_event.is_set() and not pending_confirmation:
                self.events.put(("done",))

    def _execute(self, prepared: Prepared, utterance: str):
        try:
            if self.cancel_event.is_set():
                self.events.put(("done",))
                return
            result = self.service.execute(prepared, utterance)
            if not self.cancel_event.is_set():
                self.events.put(("result", result, prepared.reply.action or "respuesta"))
        except Exception as exc:
            self.logger.error("Error al ejecutar %s: %s", prepared.reply.action, type(exc).__name__)
            self.events.put(("error", self._friendly_error(exc)))

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
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
                    self._start_voice(event[1])
                elif kind == "cancel":
                    self._cancel()
                elif kind == "status":
                    self.status.set(event[1])
                elif kind == "connection":
                    self._apply_connection(event[1])
                elif kind == "update":
                    if event[1] is None:
                        self.status.set(f"La versión {release_settings()['version']} está actualizada.")
                    else:
                        version, page = event[1]
                        self.status.set(f"Actualización {version} disponible.")
                        if messagebox.askyesno("Actualización disponible", f"Hay una versión {version}. ¿Quieres abrir la página de descarga en GitHub?", parent=self.root):
                            webbrowser.open(page)
                elif kind == "update_error":
                    self._announce_error(f"No pude buscar actualizaciones: {event[1][:180]}")
                elif kind == "transcript":
                    self._append_message("user", event[1])
                    self.command_entry.delete(0, "end")
                elif kind == "confirm":
                    prepared, utterance = event[1], event[2]
                    if self.cancel_event.is_set():
                        self._finish("Acción cancelada.", "cancelada")
                        continue
                    action = prepared.reply.action
                    detail = prepared.reply.parameters.get("text", "")[:120] if action == "write_text" else ""
                    if action == "click_control":
                        prompt = f"¿Confirmas activar el control {prepared.reply.parameters['name']} en la ventana de destino?"
                    elif action == "close_application":
                        prompt = "¿Confirmas cerrar la ventana de destino? Podría haber cambios sin guardar."
                    else:
                        prompt = f"La acción {action} puede cambiar contenido. ¿Confirmas?"
                    if detail:
                        prompt += f"\n\nTexto: {detail}"
                    self.speech.speak(prompt)
                    if messagebox.askyesno("Confirmar acción", prompt, parent=self.root):
                        threading.Thread(target=self._confirmed_worker, args=(prepared, utterance), daemon=True).start()
                    else:
                        self._finish("Acción cancelada.", "cancelada")
                elif kind == "result":
                    self._finish(event[1], event[2])
                elif kind == "error":
                    if self.cancel_event.is_set():
                        self.status.set("Acción cancelada.")
                    else:
                        self._finish(event[1], "error")
                elif kind == "done":
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

    def _finish(self, result: str, label: str):
        self.status.set(result if label == "error" else "Listo.")
        self._append_message("error" if label == "error" else "assistant", result)
        self.speech.speak(result)
        self.busy = False
        self._sync_controls()

    def _cancel(self):
        self.cancel_event.set()
        self.status.set("Cancelando; espera a que termine la petición en curso.")

    def _close(self):
        self.closed.set()
        self.cancel_event.set()
        self.hotkeys.close()
        self.speech.close()
        self.root.destroy()
