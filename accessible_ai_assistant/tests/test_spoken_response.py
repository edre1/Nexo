import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError
from actions.action_models import AIReply
from actions.action_registry import Level
from ai.gemini_provider import GeminiProvider
from ai.instructions import SPOKEN_STYLE
from ai.openai_provider import OpenAIProvider, StructuredReply
from security.security_manager import SecurityManager
from ui.main_window import MainWindow


class SpokenResponseTests(unittest.TestCase):
    def test_strips_markdown_without_changing_the_text_to_type(self):
        code = "print(`x`)  # comentario"
        reply = AIReply(
            type="action", action="write_text", parameters={"text": code},
            spoken_response="### Siguiente paso\n- **Voy a escribir** el texto en `Bloc de notas`.",
        )
        self.assertEqual(reply.spoken_response, "Siguiente paso\nVoy a escribir el texto en Bloc de notas.")
        self.assertEqual(reply.parameters["text"], code)

    def test_openai_removes_code_fences_from_chat(self):
        for message in ("```python\nsuma = a + b\n```", "´´´python suma = a + b´´´"):
            with self.subTest(message=message):
                reply = StructuredReply(
                    type="response", action=None,
                    parameters={"application": "", "name": "", "text": "", "key": ""},
                    spoken_response=message,
                )
                self.assertEqual(reply.spoken_response, "suma = a + b")

    def test_both_image_providers_use_accessible_instructions_and_plain_text(self):
        gemini = object.__new__(GeminiProvider)
        gemini.model, gemini.client = "gemini-3.5-flash-lite", Mock()
        gemini_call = gemini.client.models.generate_content
        gemini_call.return_value = SimpleNamespace(text="**Pulsa Tab** hasta escuchar Guardar.")
        self.assertEqual(gemini.describe_image(b"png", "contexto", "¿Cómo guardo?"), "Pulsa Tab hasta escuchar Guardar.")
        self.assertIn(SPOKEN_STYLE, gemini_call.call_args.kwargs["config"].system_instruction)

        luna = object.__new__(OpenAIProvider)
        luna.model, luna.client = "gpt-6-luna", Mock()
        luna_call = luna.client.responses.create
        luna_call.return_value = SimpleNamespace(output_text="**Pulsa Tab** hasta escuchar Guardar.")
        self.assertEqual(luna.describe_image(b"png", "contexto", "¿Cómo guardo?"), "Pulsa Tab hasta escuchar Guardar.")
        self.assertIn(SPOKEN_STYLE, luna_call.call_args.kwargs["instructions"])

    def test_empty_visual_action_gets_announcement_and_still_requires_confirmation(self):
        reply = AIReply.model_validate({'type': 'action', 'action': 'computer_control', 'parameters': {}, 'spoken_response': ''})
        self.assertTrue(reply.spoken_response.strip())
        self.assertEqual(SecurityManager().evaluate(reply).level, Level.CONFIRM)

    def test_openai_parser_accepts_old_empty_action_without_crashing(self):
        parsed = StructuredReply.model_validate({'type': 'action', 'action': 'computer_control', 'parameters': {'application': '', 'name': '', 'text': '', 'key': ''}, 'spoken_response': '  '})
        self.assertIn('Voy a', parsed.spoken_response)

    def test_empty_answer_is_not_invented_and_has_friendly_error(self):
        with self.assertRaises(ValidationError) as error:
            AIReply(type='response', spoken_response=' ')
        message = MainWindow._friendly_error(error.exception)
        self.assertIn('respuesta incompleta', message)
        self.assertNotIn('pydantic', message)

    def test_unknown_action_stays_rejected(self):
        with self.assertRaises(ValidationError):
            AIReply(type='action', action='delete_file', spoken_response='')
