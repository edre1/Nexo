import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ai.openai_provider import ActionParameters, OpenAIProvider, StructuredReply
from security.security_manager import SecurityManager
from actions.action_registry import Level


class OpenAIProviderTests(unittest.TestCase):
    def test_structured_action_passes_same_local_policy(self):
        provider = object.__new__(OpenAIProvider)
        provider.model = "gpt-6-luna"
        provider.client = Mock()
        provider.client.responses.parse.return_value = SimpleNamespace(output_parsed=StructuredReply(
            type="action", action="open_application",
            parameters=ActionParameters(application="notepad", name="", text="", key="", direction="", count=""),
            spoken_response="Abriré el Bloc de notas.",
        ))
        reply = provider.interpret("Abre Bloc de notas", "Escritorio", [], True)
        self.assertEqual(reply.parameters, {"application": "notepad"})
        self.assertEqual(SecurityManager().evaluate(reply, "Escritorio").level, Level.SAFE)
        kwargs = provider.client.responses.parse.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertFalse(kwargs["store"])

    def test_voice_uses_transcription_model(self):
        provider = object.__new__(OpenAIProvider)
        provider.client = Mock()
        provider.client.audio.transcriptions.create.return_value = SimpleNamespace(text="Abre el Bloc de notas")
        self.assertEqual(provider.transcribe(b"WAV", "es-MX"), "Abre el Bloc de notas")
        kwargs = provider.client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-transcribe")
        self.assertEqual(kwargs["language"], "es")


if __name__ == "__main__":
    unittest.main()
