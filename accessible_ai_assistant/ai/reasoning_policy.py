"""Local effort selection: no extra API request, no execution permissions changed."""
from dataclasses import dataclass
import re
from typing import Literal
import unicodedata


@dataclass(frozen=True)
class ReasoningChoice:
    effort: Literal["low", "medium", "high"]
    reason: str

    @property
    def label(self):
        return {"low": "bajo", "medium": "medio", "high": "alto"}[self.effort]


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def choose_reasoning(request, phase="interpret", recent="", escalate=False):
    text = normalize(request)
    if len(text.split()) <= 10 and re.search(r"\b(si|hazlo|continua|sigue|repite|igual|mismo|eso|ese|esa)\b", text) and recent:
        text += " " + normalize(recent[-4000:])
    if escalate:
        return ReasoningChoice("high", "la tarea visual ha necesitado varios pasos")
    complex_terms = r"\b(analiz\w*|compar\w*|depur\w*|diagnostic\w*|resuelv\w*|resolver|razona\w*|demuestr\w*|justific\w*|optimiza\w*|investig\w*|corrige\w*|corregir|implementa\w*|desarrolla\w*|algoritmo\w*)\b"
    multiple_steps = re.search(r"\b(despues|luego|paso a paso|a continuacion|por ultimo|al terminar)\b", text)
    verbs = re.findall(r"\b(abre|busca|encuentra|selecciona|escribe|copia|pega|guarda|rellena|completa|pulsa|haz clic|mueve|lee|revisa)\b", text)
    if re.search(complex_terms, text) or multiple_steps or len(verbs) >= 2 or len(text.split()) > 100 or "por que" in text:
        return ReasoningChoice("high", "la petición requiere análisis o varios pasos")
    if phase in {"vision", "computer"}:
        return ReasoningChoice("medium", "hay que interpretar o verificar la ventana")
    simple = re.fullmatch(r"(hola|gracias|muchas gracias|buenos dias|buenas tardes|buenas noches)[.!¡¿? ]*", text)
    simple_command = re.match(r"^(por favor[, ]+)?(abre|abrir|guarda|guardar|cierra|cerrar|sube|baja|silencia|mueve|pulsa|presiona|haz clic|escribe|lee)\b", text)
    if simple or (simple_command and len(text.split()) <= 18):
        return ReasoningChoice("low", "es una orden breve y directa")
    return ReasoningChoice("medium", "es una consulta general")
