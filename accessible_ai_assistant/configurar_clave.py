"""Keyboard accessible key setup; never prints or displays stored keys."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from dotenv import dotenv_values
from config.paths import DATA_ROOT


DESTINATION = DATA_ROOT / ".env"


def main() -> int:
    root = tk.Tk()
    root.title("Configurar claves de IA")
    root.geometry("510x290")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Pega al menos una clave. Puedes dejar en blanco la que no uses. Las claves se guardan en esta carpeta.", wraplength=465).pack(anchor="w")
    ttk.Label(frame, text="Clave de Gemini API").pack(anchor="w", pady=(12, 2))
    gemini_entry = ttk.Entry(frame, show="*", width=58)
    gemini_entry.pack(fill="x")
    ttk.Label(frame, text="Clave de OpenAI API").pack(anchor="w", pady=(12, 2))
    openai_entry = ttk.Entry(frame, show="*", width=58)
    openai_entry.pack(fill="x")
    result = {"saved": False}

    def save() -> None:
        existing = dotenv_values(DESTINATION) if DESTINATION.exists() else {}
        gemini_key = gemini_entry.get().strip() or existing.get("GEMINI_API_KEY", "")
        openai_key = openai_entry.get().strip() or existing.get("OPENAI_API_KEY", "")
        if not gemini_key and not openai_key:
            messagebox.showerror("Falta una clave", "Pega al menos una clave API.", parent=root)
            gemini_entry.focus_set()
            return
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_text(
            f"GEMINI_API_KEY={gemini_key}\nOPENAI_API_KEY={openai_key}\n", encoding="utf-8"
        )
        result["saved"] = True
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e", pady=(16, 0))
    ttk.Button(buttons, text="Guardar claves", command=save).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Cancelar", command=root.destroy).pack(side="left")
    gemini_entry.bind("<Return>", lambda _event: save())
    openai_entry.bind("<Return>", lambda _event: save())
    root.bind("<Escape>", lambda _event: root.destroy())
    gemini_entry.focus_set()
    root.mainloop()
    return 0 if result["saved"] else 1


if __name__ == "__main__":
    sys.exit(main())
