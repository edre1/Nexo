"""Local activity log that avoids storing dictated text and credentials."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
from config.paths import DATA_ROOT
from utils.error_reporting import ErrorReportHandler, get_reporter


class SafeFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno >= logging.ERROR or record.exc_info:
            error_type = record.exc_info[0].__name__ if record.exc_info else "ApplicationError"
            return f"{self.formatTime(record)} {record.levelname} {record.module}:{record.funcName} {error_type}"
        return super().format(record)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("accessible_assistant")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        try:
            folder = DATA_ROOT / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(folder / "assistant.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        except OSError:
            handler = logging.StreamHandler()
        handler.setFormatter(SafeFormatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        try:
            logger.addHandler(ErrorReportHandler(get_reporter()))
        except Exception:
            logger.warning("El registro detallado de errores no está disponible.")
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
