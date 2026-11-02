"""Compare Whisper small locally with Nexo's original Gemini transcription."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import time
import wave

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
NEXO_MODEL = LOCAL / "Nexo" / "models" / "whisper-small"
MODEL_PATH = NEXO_MODEL if (NEXO_MODEL / "model.bin").exists() else LOCAL / "PruebaWhisperSmall" / "modelo-small"
GEMINI_MODEL = "gemini-3.5-flash-lite"


def available_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    # Reuse a configured local copy, without copying or printing its key.
    from dotenv import dotenv_values
    root = Path(__file__).resolve().parent
    for path in (root / ".env", root.parent / "AsistenteAccesibleWindows" / "accessible_ai_assistant" / ".env"):
        if path.is_file():
            value = dotenv_values(path).get("GEMINI_API_KEY")
            if value:
                return value.strip()
    return ""


def wav_from_file(path):
    from faster_whisper.audio import decode_audio
    samples = decode_audio(path, sampling_rate=16000)
    audio = BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((samples.clip(-1, 1) * 32767).astype("int16").tobytes())
    return audio.getvalue()


def gemini_transcribe(audio, key):
    if not key:
        raise ValueError("Falta la clave de Gemini. Pégala en el campo Clave API.")
    from google import genai
    from google.genai import types
    start = time.perf_counter()
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000)) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=["Transcribe literalmente esta voz en es-MX. Devuelve solo las palabras pronunciadas, sin comentarios.", types.Part.from_bytes(data=audio, mime_type="audio/wav")],
            config=types.GenerateContentConfig(temperature=0),
        )
    text = (response.text or "").strip().strip('"')
    if not text:
        raise ValueError("Gemini no devolvió una transcripción.")
    return {"modelo": GEMINI_MODEL, "texto": text[:2000], "peticion_segundos": round(time.perf_counter() - start, 3)}


class Benchmark:
    def __init__(self):
        self.model = None

    def load(self):
        start = time.perf_counter()
        if not (MODEL_PATH / "model.bin").exists():
            raise ValueError("Primero pulsa Descargar modelo. Solo la descarga necesita internet.")
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(str(MODEL_PATH), device="cpu", compute_type="int8", cpu_threads=4, num_workers=1, local_files_only=True)
        return time.perf_counter() - start

    def transcribe(self, audio):
        loading = self.load()
        start = time.perf_counter()
        segments, info = self.model.transcribe(audio, language="es", beam_size=5, vad_filter=True, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
        elapsed = time.perf_counter() - start
        return {"texto": text or "[No se detectaron palabras]", "audio_segundos": round(info.duration, 3), "carga_modelo_segundos": round(loading, 3), "transcripcion_segundos": round(elapsed, 3), "total_segundos": round(loading + elapsed, 3)}

    def compare(self, audio, key="", include_gemini=True):
        report = {"comparacion": "Mismo audio WAV para ambos modelos; tiempos medidos por separado."}
        try:
            report["Whisper small (local)"] = self.transcribe(BytesIO(audio))
        except Exception as exc:
            report["Whisper small (local)"] = {"error": str(exc)}
        if include_gemini:
            try:
                report["Gemini (original de Nexo)"] = gemini_transcribe(audio, key)
            except ValueError as exc:
                report["Gemini (original de Nexo)"] = {"error": str(exc) if not key or "transcripción" in str(exc) else "Gemini rechazó la petición. Revisa la clave, el modelo y los límites de tu cuenta."}
            except Exception:
                report["Gemini (original de Nexo)"] = {"error": "No se pudo consultar Gemini. Revisa internet, la clave y los límites de tu cuenta."}
        return report


def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog

    root = tk.Tk()
    root.title("Comparación · Whisper small y Gemini")
    root.geometry("800x780")
    root.minsize(560, 480)
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Whisper small frente a Gemini", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Whisper procesa localmente. Al comparar, la misma grabación también se envía a Gemini. Solo transcribe; no ejecuta órdenes.", wraplength=700).pack(anchor="w", pady=8)
    compare = tk.BooleanVar(value=True)
    compare_box = ttk.Checkbutton(frame, text=f"Comparar también con Gemini ({GEMINI_MODEL})", variable=compare)
    compare_box.pack(anchor="w")
    ttk.Label(frame, text="Clave API de Gemini · no se guarda ni aparece en los resultados").pack(anchor="w", pady=(6, 0))
    key_entry = ttk.Entry(frame, show="*")
    key_entry.insert(0, available_key())
    key_entry.pack(fill="x", pady=5)
    status = tk.StringVar(value="Listo. F2 inicia o detiene la grabación; F3 abre un archivo.")
    ttk.Label(frame, textvariable=status, wraplength=700).pack(anchor="w", pady=8)
    ttk.Label(frame, text="Tiempo máximo de grabación (segundos)").pack(anchor="w")
    duration = ttk.Spinbox(frame, from_=3, to=120, width=10)
    duration.set(30)
    duration.pack(anchor="w", pady=5)
    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=12)
    ttk.Label(frame, text="Resultados · F6 para enfocar, Ctrl+C para copiar").pack(anchor="w")
    results = tk.Text(frame, wrap="word", font=("Segoe UI", 12), height=12)
    results.pack(fill="both", expand=True, pady=8)
    results.bind("<KeyPress>", lambda e: None if (e.state & 4 and e.keysym.lower() == "c") or e.keysym in {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Tab", "F2", "F3", "F6"} else "break")
    results.bind("<Tab>", lambda _e: (record_button.focus_set(), "break")[-1])
    results.bind("<Shift-Tab>", lambda _e: (download_button.focus_set(), "break")[-1])
    ttk.Label(frame, text=f"Modelo local: {MODEL_PATH}", wraplength=700).pack(anchor="w")
    events = Queue()
    stop = threading.Event()
    state = {"busy": False, "recording": False, "closed": False}
    benchmark = Benchmark()

    def controls(busy):
        state["busy"] = busy
        for button in (record_button, file_button, download_button):
            button.config(state="disabled" if busy else "normal")
        key_entry.config(state="disabled" if busy else "normal")
        compare_box.config(state="disabled" if busy else "normal")

    def start_work(work):
        controls(True)
        def worker():
            try:
                events.put(("result", work()))
            except Exception as exc:
                events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def record():
        if state["recording"]:
            stop.set()
            record_button.config(state="disabled")
            return
        if state["busy"]:
            return
        try:
            seconds = int(duration.get())
            if not 3 <= seconds <= 120:
                raise ValueError()
        except ValueError:
            status.set("Elige un tiempo entre 3 y 120 segundos.")
            return
        stop.clear()
        api_key, use_gemini = key_entry.get().strip(), compare.get()
        state["recording"] = True
        def work():
            try:
                benchmark.load()  # Load before asking the user to speak.
            except Exception:
                pass  # Show an independent error for Whisper in the comparison.
            if stop.is_set():
                raise ValueError("Grabación cancelada antes de abrir el micrófono.")
            import sounddevice as sd
            chunks = []
            with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1600) as stream:
                events.put(("recording", None))
                for _ in range(seconds * 10):
                    if stop.is_set():
                        break
                    data, overflow = stream.read(1600)
                    if overflow:
                        raise RuntimeError("Se perdieron muestras de audio. Cierra otras aplicaciones e inténtalo de nuevo.")
                    chunks.append(bytes(data))
            events.put(("processing", None))
            if not chunks:
                raise ValueError("No se grabó audio.")
            audio = BytesIO()
            with wave.open(audio, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"".join(chunks))
            audio.seek(0)
            return benchmark.compare(audio.getvalue(), api_key, use_gemini)
        status.set("Cargando modelo; espera el aviso Habla ahora.")
        start_work(work)

    def open_file():
        if state["busy"]:
            return
        path = filedialog.askopenfilename(parent=root, title="Selecciona audio", filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.ogg"), ("Todos", "*.*")])
        if path:
            api_key, use_gemini = key_entry.get().strip(), compare.get()
            status.set("Comparando el archivo de audio…")
            start_work(lambda: benchmark.compare(wav_from_file(path), api_key, use_gemini))

    def download():
        if state["busy"]:
            return
        def work():
            from faster_whisper.utils import download_model
            download_model("small", output_dir=str(MODEL_PATH))
            return {"aviso": "Modelo descargado. Ya puedes transcribir sin internet."}
        status.set("Descargando Whisper small. Puede tardar varios minutos.")
        start_work(work)

    def drain():
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "recording":
                status.set("Habla ahora. F2 o Detener finaliza la grabación y transcribe.")
                record_button.config(text="Detener (F2)", state="normal")
                root.bell()
            elif kind == "processing":
                state["recording"] = False
                record_button.config(state="disabled")
                status.set("Transcribiendo con los modelos elegidos…")
            else:
                state["recording"] = False
                controls(False)
                record_button.config(text="Grabar (F2)")
                if kind == "error":
                    status.set("Error: " + value)
                else:
                    results.insert("end", json.dumps(value, ensure_ascii=False, indent=2) + "\n\n")
                    results.see("end")
                    status.set("Prueba terminada. Puedes repetir para comparar con el modelo ya cargado.")
        if not state["closed"]:
            root.after(100, drain)

    record_button = ttk.Button(bar, text="Grabar (F2)", command=record)
    record_button.pack(side="left", padx=(0, 8))
    file_button = ttk.Button(bar, text="Abrir audio (F3)", command=open_file)
    file_button.pack(side="left", padx=(0, 8))
    download_button = ttk.Button(bar, text="Descargar modelo", command=download)
    download_button.pack(side="left")
    root.bind("<F2>", lambda _e: record())
    root.bind("<F3>", lambda _e: open_file())
    root.bind("<F6>", lambda _e: results.focus_set())
    def close():
        state["closed"] = True
        stop.set()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, drain)
    record_button.focus_set()
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archivo", help="Transcribe un archivo y muestra mediciones en consola, sin abrir la interfaz.")
    parser.add_argument("--comparar", action="store_true", help="También envía el mismo audio a Gemini; usa GEMINI_API_KEY o la clave local de Nexo.")
    args = parser.parse_args()
    if args.archivo:
        print(json.dumps(Benchmark().compare(wav_from_file(args.archivo), available_key(), args.comparar), ensure_ascii=False, indent=2))
    else:
        run_gui()
