"""Keyboard navigable Tk interface. All Tk changes happen on the main thread."""
from queue import Empty, Queue
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk
import win32con
import win32gui
import pythoncom

from actions.action_registry import Level
from assistant_service import AssistantService, Prepared
from config.settings import Settings
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
            self.status.set(str(exc))
            self.logger.error("Fallo de atajo global: %s", type(exc).__name__)
        self.root.after(100, self._drain)
        self.root.after(500, self._track_target)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        self.root.title("Nexo")
        self.root.geometry("680x680")
        self.root.minsize(520, 500)
        body = ttk.Frame(self.root, padding=16)
        body.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Iniciando asistente.")
        ttk.Label(body, text="Estado del asistente").pack(anchor="w")
        ttk.Label(body, textvariable=self.status, wraplength=620).pack(anchor="w", pady=(0, 10))
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
        ttk.Button(buttons, text="Buscar actualizaciones", command=self._check_updates).pack(side="left", padx=(8, 0))
        ttk.Label(body, text="Escribe una petición para probar sin micrófono").pack(anchor="w")
        self.command_entry = ttk.Entry(body)
        self.command_entry.pack(fill="x", pady=(0, 5))
        self.command_entry.bind("<Return>", lambda _event: self._start_text())
        ttk.Button(body, text="Enviar petición escrita", command=self._start_text).pack(anchor="w", pady=(0, 10))
        ttk.Label(body, text="Texto entendido del usuario").pack(anchor="w")
        self.transcript = tk.Text(body, height=3, wrap="word", takefocus=True)
        self.transcript.pack(fill="x", pady=(0, 10))
        self.transcript.config(state="disabled")
        ttk.Label(body, text="Respuesta del asistente").pack(anchor="w")
        self.response = tk.Text(body, height=4, wrap="word", takefocus=True)
        self.response.pack(fill="x", pady=(0, 10))
        self.response.config(state="disabled")
        ttk.Label(body, text="Registro de las últimas acciones").pack(anchor="w")
        self.history = tk.Listbox(body, height=7)
        self.history.pack(fill="both", expand=True)
        self.command_entry.focus_set()
        self.root.bind("<Escape>", lambda _event: self._cancel())

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _target(self) -> int:
        active = win32gui.GetForegroundWindow()
        if active and active != self.own_hwnd:
            self.last_target = active
        return self.last_target

    def _check_updates(self):
        if self.busy:
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
            self.status.set(f"Falta la clave de {'OpenAI' if requested == 'openai' else 'Gemini'}. Agrégala en .env y reinicia.")
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
        if self.busy:
            return
        target = self._target() if target is None else target
        self.busy = True
        self.cancel_event.clear()
        self.status.set("Preparando micrófono.")
        self.listen_button.config(state="disabled")
        self.provider_combo.config(state="disabled")
        threading.Thread(target=self._worker, args=(None, target), daemon=True).start()

    def _start_text(self):
        if self.busy:
            return
        utterance = self.command_entry.get().strip()
        if not utterance:
            self.status.set("Escribe una petición primero.")
            return
        target = self._target()
        self.busy = True
        self.cancel_event.clear()
        self.listen_button.config(state="disabled")
        self.provider_combo.config(state="disabled")
        threading.Thread(target=self._worker, args=(utterance, target), daemon=True).start()

    def _worker(self, utterance: str | None, target: int):
        pythoncom.CoInitialize()
        pending_confirmation = False
        try:
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
                elif kind == "update":
                    if event[1] is None:
                        self.status.set(f"La versión {release_settings()['version']} está actualizada.")
                    else:
                        version, page = event[1]
                        self.status.set(f"Actualización {version} disponible.")
                        if messagebox.askyesno("Actualización disponible", f"Hay una versión {version}. ¿Quieres abrir la página de descarga en GitHub?", parent=self.root):
                            webbrowser.open(page)
                elif kind == "update_error":
                    self.status.set(f"No pude buscar actualizaciones: {event[1][:180]}")
                elif kind == "transcript":
                    self._set_text(self.transcript, event[1])
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
                    self.listen_button.config(state="normal")
                    self.provider_combo.config(state="readonly")
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
        self.status.set("Listo.")
        self._set_text(self.response, result)
        self.history.insert(0, f"{label}: {result[:120]}")
        while self.history.size() > 20:
            self.history.delete("end")
        self.speech.speak(result)
        self.busy = False
        self.listen_button.config(state="normal")
        self.provider_combo.config(state="readonly")

    def _cancel(self):
        self.cancel_event.set()
        self.status.set("Cancelando; espera a que termine la petición en curso.")

    def _close(self):
        self.cancel_event.set()
        self.hotkeys.close()
        self.speech.close()
        self.root.destroy()
