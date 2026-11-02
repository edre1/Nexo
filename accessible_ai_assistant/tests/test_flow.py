import logging
import unittest

from actions.action_models import AIReply
from actions.action_registry import Level
from assistant_service import AssistantService
from security.security_manager import SecurityManager


class FakeProvider:
    def interpret(self, utterance, context, history, learning_mode):
        return AIReply(type="action", action="open_application", parameters={"application": "notepad"}, spoken_response="Abriré Bloc de notas.")


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, reply, hwnd):
        self.calls.append((reply.action, hwnd))
        return "Bloc de notas abierto."


class FlowTests(unittest.TestCase):
    def test_interpret_security_execute(self):
        executor = FakeExecutor()
        service = AssistantService(FakeProvider(), SecurityManager(), executor, logging.getLogger("test"), True)
        prepared = service.prepare("Abre Bloc de notas", "Ventana: Escritorio", 123)
        self.assertEqual(prepared.decision.level, Level.SAFE)
        self.assertEqual(service.execute(prepared, "Abre Bloc de notas"), "Bloc de notas abierto.")
        self.assertEqual(executor.calls, [("open_application", 123)])


if __name__ == "__main__":
    unittest.main()
