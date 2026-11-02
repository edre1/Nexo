import logging
import unittest

from actions.action_models import AIReply
from assistant_service import AssistantService
from security.security_manager import SecurityManager


class ScreenProvider:
    def interpret(self, *_args):
        return AIReply(type="action", action="get_screen_description", spoken_response="Voy a revisar la pantalla.")


class ScreenExecutor:
    def __init__(self):
        self.question = None

    def execute(self, _reply, _target, question=""):
        self.question = question
        return "La fecha visible es el 1 de noviembre."


class ScreenQuestionTests(unittest.TestCase):
    def test_original_question_reaches_visual_analysis(self):
        executor = ScreenExecutor()
        service = AssistantService(ScreenProvider(), SecurityManager(), executor, logging.getLogger("screen-test"), True)
        question = "¿Qué fecha aparece en la pantalla?"
        prepared = service.prepare(question, "Ventana de destino: documento", 42)
        result = service.execute(prepared, question)
        self.assertEqual(executor.question, question)
        self.assertIn("1 de noviembre", result)


if __name__ == "__main__":
    unittest.main()
