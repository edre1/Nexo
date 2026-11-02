"""Local model storage. Downloads happen only on explicit setup, never during speech."""
import os
from pathlib import Path
from urllib.request import urlopen

MODELS = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Nexo" / "models"
PIPER = MODELS / "es_MX-claude-high.onnx"
VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/"


def download_models(progress=lambda _text: None):
    MODELS.mkdir(parents=True, exist_ok=True)
    progress("Descargando la voz Claude high de Piper en español de México.")
    for name in (PIPER.name, PIPER.name + ".json", "MODEL_CARD"):
        target = MODELS / (PIPER.stem + ".MODEL_CARD.txt" if name == "MODEL_CARD" else name)
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

