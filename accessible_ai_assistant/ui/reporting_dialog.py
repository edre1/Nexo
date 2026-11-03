"""Keyboard accessible local email setup; SMTP work stays off the Tk thread."""
import json
import logging
from queue import Queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk


def reporting_dialog(root, reporter, notice):
    settings = reporter.settings()
    dialog = tk.Toplevel(root)
    dialog.title("Nexo · Reportes de errores")
    dialog.transient(root)
    dialog.grab_set()
    body = ttk.Frame(dialog, padding=20)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Envía un resumen técnico de los errores a tu correo.", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    ttk.Label(body, text="No incluye claves, conversaciones, audio, capturas ni rutas personales. Los errores quedan guardados si falla el envío.", wraplength=560).pack(anchor="w", pady=8)
    enabled = tk.BooleanVar(value=settings["enabled"])
    ttk.Checkbutton(body, text="Activar envío automático de reportes (máximo un resumen por hora)", variable=enabled).pack(anchor="w", pady=8)
    entries = {}
    for key, label in (("recipient", "Recibir reportes en"), ("sender", "Cuenta de correo que enviará los reportes"), ("host", "Servidor SMTP")):
        ttk.Label(body, text=label).pack(anchor="w")
        entry = ttk.Entry(body, width=64)
        entry.insert(0, settings[key])
        entry.pack(fill="x", pady=(3, 8))
        entries[key] = entry
    ttk.Label(body, text="Puerto seguro").pack(anchor="w")
    port = ttk.Combobox(body, state="readonly", values=("587", "465"), width=12)
    port.set(str(settings["port"]))
    port.pack(anchor="w", pady=(3, 8))
    ttk.Label(body, text="Contraseña de aplicación del correo · deja vacío para conservar la guardada").pack(anchor="w")
    password = ttk.Entry(body, show="*", width=64)
    password.pack(fill="x", pady=(3, 8))
    ttk.Label(body, text="En Gmail utiliza una contraseña de aplicación, no tu contraseña normal. La credencial se protege con Windows y se configura en la laptop de destino.", wraplength=560).pack(anchor="w", pady=(0, 8))
    status = tk.StringVar(value=f"Grupos pendientes: {len(reporter.reports(pending_only=True))}. " + reporter._metadata("delivery_status"))
    ttk.Label(body, textvariable=status, wraplength=560).pack(anchor="w", pady=8)
    events = Queue()
    state = {"closed": False, "busy": False}

    def save():
        try:
            value = {key: entry.get() for key, entry in entries.items()}
            value.update(enabled=enabled.get(), port=int(port.get()))
            reporter.save_settings(value, password.get())
            password.delete(0, "end")
            reporter.retry_soon()
            status.set("Configuración guardada. Usa Enviar prueba para comprobarla.")
            notice("Configuración de reportes guardada.")
            return True
        except Exception as exc:
            logging.getLogger("accessible_assistant").error("report_settings_failed", exc_info=True)
            text = str(exc) if isinstance(exc, ValueError) else "No pude guardar la configuración de reportes."
            status.set(text)
            notice(text, True)
            return False

    def send(test):
        if state["busy"] or not save():
            return
        state["busy"] = True
        status.set("Enviando correo. Espera unos segundos.")
        for button in buttons:
            button.config(state="disabled")
        def worker():
            try:
                if test:
                    reporter.send_test()
                    text = "Correo de prueba enviado. Revisa tu bandeja y la carpeta de spam."
                else:
                    number = reporter.send_pending(force=True)
                    text = f"Grupos de errores enviados: {number}."
                events.put((text, False))
            except Exception:
                logging.getLogger("accessible_assistant").error("manual_report_delivery_failed", exc_info=True)
                events.put(("No pude enviar el correo. Revisa la conexión, la cuenta y su contraseña de aplicación. Los reportes siguen guardados.", True))
        threading.Thread(target=worker, daemon=True).start()

    def export():
        path = filedialog.asksaveasfilename(parent=dialog, title="Exportar reportes de Nexo", defaultextension=".json", initialfile="Nexo-reportes.json", filetypes=[("Reportes JSON", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as output:
                    json.dump(reporter.reports(), output, ensure_ascii=False, indent=2)
                notice("Reportes exportados.")
            except Exception:
                logging.getLogger("accessible_assistant").error("report_export_failed", exc_info=True)
                notice("No pude exportar los reportes.", True)

    bar = ttk.Frame(body)
    bar.pack(fill="x", pady=10)
    buttons = []
    for label, callback in (("Guardar", save), ("Enviar prueba", lambda: send(True)), ("Enviar pendientes", lambda: send(False)), ("Exportar", export)):
        button = ttk.Button(bar, text=label, command=callback)
        button.pack(side="left", padx=(0, 6))
        buttons.append(button)

    def close():
        state["closed"] = True
        dialog.destroy()
    ttk.Button(body, text="Cerrar", command=close).pack(anchor="e")
    def drain():
        while not events.empty():
            text, error = events.get_nowait()
            state["busy"] = False
            status.set(text)
            notice(text, error)
            for button in buttons:
                button.config(state="normal")
        if not state["closed"]:
            dialog.after(100, drain)
    dialog.protocol("WM_DELETE_WINDOW", close)
    dialog.bind("<Escape>", lambda _e: close())
    dialog.after(100, drain)
    entries["recipient"].focus_set()
    root.wait_window(dialog)
