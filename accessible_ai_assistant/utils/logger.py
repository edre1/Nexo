"""Local activity log that avoids storing dictated text and credentials."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
from config.paths import DATA_ROOT


def setup_logger() -> logging.Logger:
    folder = DATA_ROOT / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("accessible_assistant")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(folder / "assistant.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def safe_transcript(text: str) -> str:
    # Log only a tiny allowlist of phrases that cannot contain dictated content.
    normalized = re.sub(r"\s+", " ", text.strip().casefold()).strip(" .?!¡¿")
    simple = {
        "qué ventana tengo abierta", "que ventana tengo abierta",
        "dónde está el foco", "donde esta el foco",
        "qué controles hay", "que controles hay", "sube el volumen",
        "baja el volumen", "silencia el volumen", "guarda el archivo",
    }
    if normalized in simple or re.fullmatch(r"abre (el )?(bloc de notas|chrome|visual studio code|vs code|edge|explorador de archivos|calculadora)", normalized):
        return text[:100]
    return "<contenido omitido>"
