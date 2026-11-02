"""Local model storage. Downloads happen only on explicit setup, never during speech."""
import os
from pathlib import Path
from urllib.request import urlopen

MODELS = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Nexo" / "models"
WHISPER = MODELS / "whisper-base"
PIPER = MODELS / "es_MX-ald-medium.onnx"
VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/"


def download_models(progress=lambda _text: None):
    MODELS.mkdir(parents=True, exist_ok=True)
    progress("Descargando Whisper base. La primera descarga puede tardar varios minutos.")
    from faster_whisper.utils import download_model
    download_model("base", output_dir=str(WHISPER))
    progress("Descargando la voz de Piper en español de México.")
    for name in (PIPER.name, PIPER.name + ".json", "MODEL_CARD"):
        target = MODELS / ("Piper-MODEL_CARD.txt" if name == "MODEL_CARD" else name)
        if target.exists():
            continue
        temp = target.with_suffix(target.suffix + ".part")
        try:
            with urlopen(VOICE_BASE + name, timeout=60) as response, temp.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)


class WhisperTranscriber:
    def __init__(self):
        self.model = None

    def transcribe(self, wav_bytes, language):
        if not (WHISPER / "model.bin").exists():
            raise ValueError("Falta Whisper. Abre Configuración y pulsa Descargar modelos locales.")
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(str(WHISPER), device="cpu", compute_type="int8", cpu_threads=4, num_workers=1, local_files_only=True)
        from io import BytesIO
        segments, _info = self.model.transcribe(
            BytesIO(wav_bytes), language=language.split("-")[0], beam_size=3,
            vad_filter=True, condition_on_previous_text=False,
            initial_prompt="Nombres: Nexo, Bloc de notas, Chrome, Word, Visual Studio Code.",
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError("Whisper no detectó palabras. Inténtalo de nuevo.")
        return text[:2000]
