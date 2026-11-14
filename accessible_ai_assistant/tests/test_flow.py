import logging
import unittest
from unittest.mock import Mock

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
    def test_educational_requests_skip_extra_permission_when_disabled(self):
        provider = Mock(wraps=FakeProvider())
        guard = SecurityManager(require_confirmation=False)
        service = AssistantService(provider, guard, FakeExecutor(), logging.getLogger("test"), True)
        service.prepare("Escribe un ejemplo HTML", "Bloc de notas", 123)
        self.assertFalse(provider.interpret.call_args.args[-1])
        guard.require_confirmation = True
        service.prepare("Escribe un ejemplo HTML", "Bloc de notas", 123)
        self.assertTrue(provider.interpret.call_args.args[-1])

    def test_interpret_security_execute(self):
        executor = FakeExecutor()
        service = AssistantService(FakeProvider(), SecurityManager(), executor, logging.getLogger("test"), True)
        prepared = service.prepare("Abre Bloc de notas", "Ventana: Escritorio", 123)
        self.assertEqual(prepared.decision.level, Level.SAFE)
        self.assertEqual(service.execute(prepared, "Abre Bloc de notas"), "Bloc de notas abierto.")
        self.assertEqual(executor.calls, [("open_application", 123)])


if __name__ == "__main__":
    unittest.main()
