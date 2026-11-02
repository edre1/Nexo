import unittest
from pydantic import ValidationError

from actions.action_models import AIReply
from actions.action_registry import Level
from security.security_manager import SecurityManager


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.guard = SecurityManager()

    def action(self, name, parameters=None):
        return AIReply(type="action", action=name, parameters=parameters or {}, spoken_response="Listo.")

    def test_allowed_open(self):
        self.assertEqual(self.guard.evaluate(self.action("open_application", {"application": "notepad"})).level, Level.SAFE)

    def test_unknown_app_and_extra_parameter_blocked(self):
        self.assertEqual(self.guard.evaluate(self.action("open_application", {"application": "powershell"})).level, Level.BLOCKED)
        self.assertEqual(self.guard.evaluate(self.action("open_application", {"application": "notepad", "path": "x"})).level, Level.BLOCKED)

    def test_write_needs_confirmation(self):
        self.assertEqual(self.guard.evaluate(self.action("write_text", {"text": "Hola mundo"})).level, Level.CONFIRM)

    def test_dangerous_shortcut_blocked(self):
        self.assertEqual(self.guard.evaluate(self.action("press_key", {"key": "Win+R"})).level, Level.BLOCKED)

    def test_terminal_input_blocked(self):
        self.assertEqual(self.guard.evaluate(self.action("write_text", {"text": "dir\n"}), "Windows Terminal").level, Level.BLOCKED)

    def test_cursor_movement_is_bounded(self):
        self.assertEqual(self.guard.evaluate(self.action("move_cursor", {"direction": "left", "count": "3"})).level, Level.SAFE)
        self.assertEqual(self.guard.evaluate(self.action("move_cursor", {"direction": "left", "count": "500"})).level, Level.BLOCKED)
        self.assertEqual(self.guard.evaluate(self.action("move_cursor", {"direction": "escape", "count": "1"})).level, Level.BLOCKED)

    def test_click_uses_navigation_allowlist_and_confirmation(self):
        self.assertEqual(self.guard.evaluate(self.action("click_control", {"name": "Archivo"})).level, Level.CONFIRM)
        self.assertEqual(self.guard.evaluate(self.action("click_control", {"name": "Eliminar"})).level, Level.BLOCKED)
        self.assertEqual(self.guard.evaluate(self.action("click_control", {"name": "Aceptar"})).level, Level.BLOCKED)

    def test_unknown_action_rejected_by_model(self):
        with self.assertRaises(ValidationError):
            self.action("delete_file", {"path": "C:\\"})

    def test_response_cannot_carry_action(self):
        with self.assertRaises(ValidationError):
            AIReply(type="response", action="open_application", spoken_response="Hola")


if __name__ == "__main__":
    unittest.main()
