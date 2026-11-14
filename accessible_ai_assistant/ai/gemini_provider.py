"""Official Google GenAI SDK adapter. No OS access here."""
from google import genai
from google.genai import types
from actions.action_models import AIReply
from actions.action_registry import CATALOG
from ai.base_provider import AIProvider
from ai.instructions import action_instructions, screen_instructions
from utils.spoken_text import plain_spoken_text


REPLY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING", "enum": ["action", "response"]},
        "action": {"type": "STRING", "enum": [name for name in CATALOG if name != "computer_control"]},
        "parameters": {
            "type": "OBJECT",
            "properties": {key: {"type": "STRING"} for key in ("application", "name", "text", "key")},
        },
        "spoken_response": {"type": "STRING"},
    },
    "required": ["type", "spoken_response"],
}


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY. Consulta el archivo README.md.")
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
        self.model = model

    def interpret(self, utterance: str, context: str, history: list[tuple[str, str]], learning_mode: bool) -> AIReply:
        recent = "\n".join(f"Usuario: {u}\nAsistente: {a}" for u, a in history[-3:])
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"Contexto accesible actual: {context}\nDiálogo reciente: {recent}\nPetición: {utterance}",
            config=types.GenerateContentConfig(
                system_instruction=action_instructions(learning_mode) + " El proveedor actual es Gemini: computer_control no está disponible. Si te piden mover el ratón o una tarea visual fuera del catálogo, responde que seleccionen GPT-6 Luna para usar el control visual.",
                response_mime_type="application/json",
                response_schema=REPLY_SCHEMA,
                temperature=0,
            ),
        )
        if not response.text:
            raise ValueError("Gemini no devolvió contenido.")
        return AIReply.model_validate_json(response.text)

    def transcribe(self, wav_bytes: bytes, language: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                f"Transcribe literalmente esta voz en {language}. Devuelve solo las palabras pronunciadas, sin comentarios.",
                types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
            ],
            config=types.GenerateContentConfig(temperature=0),
        )
        text = (response.text or "").strip().strip('"')
        if not text:
            raise ValueError("No se reconoció ninguna palabra.")
        return text[:2000]

    def describe_image(self, png_bytes: bytes, context: str, question: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                f"Pregunta del usuario: {question}\nContexto de accesibilidad: {context}",
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            ],
            config=types.GenerateContentConfig(system_instruction=screen_instructions(), temperature=0),
        )
        return plain_spoken_text(response.text or "")[:1200] or "No pude responder la pregunta sobre la pantalla."
