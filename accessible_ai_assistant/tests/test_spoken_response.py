import unittest
from pydantic import ValidationError
from actions.action_models import AIReply
from actions.action_registry import Level
from ai.openai_provider import StructuredReply
from security.security_manager import SecurityManager
from ui.main_window import MainWindow


class SpokenResponseTests(unittest.TestCase):
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
