import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from config.settings import load_settings
from actions.action_models import AIReply
from actions.action_registry import Level
from assistant_service import Prepared
from security.security_manager import Decision
from ui.main_window import MainWindow


class ChatUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.speech = Mock()
        with patch("ui.main_window.GlobalHotkeys"), patch("ui.main_window.microphone_status", return_value="Disponible"), patch.object(MainWindow, "_monitor_connection"):
            self.window = MainWindow(self.root, load_settings(), Mock(), self.speech, Mock(), Mock(), Mock(), {"gemini": Mock()}, "gemini")

    def tearDown(self):
        self.window._close()

    def test_offline_blocks_entry_and_hotkey_and_announces_once(self):
        self.window._apply_connection(False)
        self.window._apply_connection(False)
        self.assertEqual(str(self.window.send_button["state"]), "disabled")
        self.assertEqual(str(self.window.listen_button["state"]), "disabled")
        self.assertEqual(self.speech.speak.call_count, 1)
        self.window.command_entry.insert(0, "Hola")
        with patch("ui.main_window.threading.Thread") as thread:
            self.window._start_text()
            self.window._start_voice(42)
            thread.assert_not_called()
        self.assertEqual(self.window.command_entry.get(), "Hola")

    def test_reconnect_and_completion_keep_offline_controls_disabled(self):
        self.window._apply_connection(True)
        self.assertEqual(str(self.window.send_button["state"]), "normal")
        self.window.busy = True
        self.window._apply_connection(False)
        self.window._finish("Error de prueba", "error")
        self.assertEqual(str(self.window.send_button["state"]), "disabled")
        self.assertIn("Error de prueba", self.window.chat.get("1.0", "end"))
        self.speech.speak.assert_called_with("Error de prueba")

    def test_chat_navigation_reads_messages(self):
        self.window._append_message("user", "Mi pregunta")
        self.window._append_message("assistant", "Mi respuesta")
        self.window._read_message(-1)
        self.speech.speak.assert_called_with("Tú: Mi pregunta")

    def test_blocked_visual_request_never_constructs_driver(self):
        self.window.selected = "openai"
        prepared = Prepared(AIReply(type="action", action="computer_control", spoken_response="Revisaré."), Decision(Level.BLOCKED, "Bloqueado"), 42)
        self.window.service.execute.return_value = "Bloqueado"
        with patch("ui.main_window.ComputerDriver") as driver:
            self.window._execute(prepared, "Haz clic")
        driver.assert_not_called()

    def test_cancel_hotkey_sets_event_without_waiting_for_ui_dialog(self):
        with patch.object(self.window, "_target", return_value=42):
            self.window._hotkey_event("cancel")
        self.assertTrue(self.window.cancel_event.is_set())


if __name__ == "__main__":
    unittest.main()
