"""OpenAI adapter. It returns data only; Windows actions remain locally validated."""
import base64

from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from actions.action_models import AIReply, ActionName
from ai.base_provider import AIProvider
from ai.instructions import action_instructions, screen_instructions


class ActionParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application: str
    name: str
    text: str
    key: str
    direction: str
    count: str


class StructuredReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    action: ActionName | None
    parameters: ActionParameters
    spoken_response: str


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-6-luna"):
        if not api_key:
            raise ValueError("Falta OPENAI_API_KEY. Consulta README.md.")
        self.client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        self.model = model

    def interpret(self, utterance: str, context: str, history: list[tuple[str, str]], learning_mode: bool) -> AIReply:
        recent = "\n".join(f"Usuario: {u}\nAsistente: {a}" for u, a in history[-3:])
        response = self.client.responses.parse(
            model=self.model,
            instructions=action_instructions(learning_mode) + (
                " Devuelve todos los campos de parameters como cadenas vacías salvo los necesarios "
                "para la acción elegida. Si respondes sin acción, action debe ser null."
            ),
            input=f"Contexto accesible actual: {context}\nDiálogo reciente: {recent}\nPetición: {utterance}",
            text_format=StructuredReply,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI no devolvió una respuesta utilizable.")
        return AIReply.model_validate({
            "type": parsed.type,
            "action": parsed.action,
            "parameters": {key: value for key, value in parsed.parameters.model_dump().items() if value},
            "spoken_response": parsed.spoken_response,
        })

    def transcribe(self, wav_bytes: bytes, language: str) -> str:
        result = self.client.audio.transcriptions.create(
            model="gpt-transcribe",
            file=("speech.wav", wav_bytes, "audio/wav"),
            language=language.split("-")[0],
        )
        text = (result.text or "").strip()
        if not text:
            raise ValueError("No se reconoció ninguna palabra.")
        return text[:2000]

    def describe_image(self, png_bytes: bytes, context: str, question: str) -> str:
        image_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
        response = self.client.responses.create(
            model=self.model,
            instructions=screen_instructions(),
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": f"Pregunta del usuario: {question}\nContexto de accesibilidad: {context}"},
                {"type": "input_image", "image_url": image_url},
            ]}],
            store=False,
        )
        return (response.output_text or "No pude describir la imagen.").strip()[:1200]
