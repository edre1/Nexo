"""Official Google GenAI SDK adapter. No OS access here."""
from google import genai
from google.genai import types
from actions.action_models import AIReply
from actions.action_registry import CATALOG
from ai.base_provider import AIProvider
from ai.instructions import action_instructions, screen_instructions


REPLY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING", "enum": ["action", "response"]},
        "action": {"type": "STRING", "enum": list(CATALOG)},
        "parameters": {
            "type": "OBJECT",
            "properties": {key: {"type": "STRING"} for key in ("application", "name", "text", "key", "direction", "count")},
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
                system_instruction=action_instructions(learning_mode),
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
                f"{screen_instructions()}\nPregunta del usuario: {question}\nContexto de accesibilidad: {context}",
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            ],
            config=types.GenerateContentConfig(temperature=0),
        )
        return (response.text or "No pude describir la imagen.").strip()[:1200]
