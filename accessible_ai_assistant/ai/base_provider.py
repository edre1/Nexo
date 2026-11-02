from abc import ABC, abstractmethod
from actions.action_models import AIReply


class AIProvider(ABC):
    @abstractmethod
    def interpret(self, utterance: str, context: str, history: list[tuple[str, str]], learning_mode: bool) -> AIReply:
        """Return one validated action or a spoken response."""

    @abstractmethod
    def transcribe(self, wav_bytes: bytes, language: str) -> str:
        """Transcribe microphone audio."""

    @abstractmethod
    def describe_image(self, png_bytes: bytes, context: str, question: str) -> str:
        """Answer the user's question using one on-demand screenshot."""
