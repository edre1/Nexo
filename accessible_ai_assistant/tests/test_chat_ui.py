import tkinter as tk
import httpx
from openai import RateLimitError
from dataclasses import replace
from threading import Event
import unittest
from unittest.mock import Mock, patch

from config.settings import load_settings
from actions.action_models import AIReply
from actions.action_registry import Level
from assistant_service import Prepared
from security.security_manager import Decision
from ui.main_window import MainWindow


class ChatUITests(unittest.TestCase):
    def test_exhausted_credits_switches_to_gemini_and_replays_text(self):
        self.window.providers["openai"] = Mock()
        self.window._set_provider("openai")
        self.window.busy = True
        with patch("ui.main_window.threading.Thread") as thread:
            self.window._handle_credits_exhausted("Mi consulta", 42, False)
            self.assertEqual(thread.call_args.kwargs["args"], ("Mi consulta", 42, True))
        self.assertEqual(self.window.selected, "gemini")
        self.assertIs(self.window.recognizer.provider, self.window.providers["gemini"])
        self.speech.speak.assert_called_with("Se agotaron los créditos de OpenAI. Cambié a Gemini.")

    def test_rate_limit_does_not_trigger_credit_fallback(self):
        self.window.providers["openai"] = Mock()
        self.window._set_provider("openai")
        response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com"))
        self.window.service.prepare.side_effect = RateLimitError(
            "429", response=response, body={"code": "rate_limit_exceeded"},
        )
        with patch("ui.main_window.internet_available", return_value=True):
            self.window._worker("Mi consulta", 0)
        self.window._drain()
        self.assertEqual(self.window.selected, "openai")
        self.assertIn("límite del proveedor", self.speech.speak.call_args.args[0])

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
        self.speech.interrupt_and_speak.assert_called_with("Tú: Mi pregunta")

    def test_conversation_history_is_read_only(self):
        self.window._append_message("assistant", "Mensaje original")
        chat = self.window.chat
        original = chat.get("1.0", "end")
        chat.insert("end", "Edición")
        chat.delete("1.0", "end")
        self.assertEqual(chat.get("1.0", "end"), original)
        self.assertEqual(str(chat["state"]), "disabled")

    def test_global_provider_shortcut_updates_chat_actions_and_transcription(self):
        luna = self.window.providers["openai"] = Mock()
        gemini = self.window.providers["gemini"]
        for index, name, provider, announcement in (
            (1, "openai", luna, "Luna. Configurado para peticiones complejas."),
            (0, "gemini", gemini, "Gemini. Configurado para preguntas sencillas."),
        ):
            self.window._hotkey_event("switch_provider")
            self.window._drain()
            self.assertEqual(self.window.selected, name)
            self.assertEqual(self.window.provider_combo.current(), index)
            self.assertIs(self.window.service.provider, provider)
            self.assertIs(self.window.service.executor.provider, provider)
            self.assertIs(self.window.recognizer.provider, provider)
            self.speech.speak.assert_called_with(announcement)

    def test_shortcut_keeps_the_available_provider_when_the_other_key_is_missing(self):
        self.window._hotkey_event("switch_provider")
        self.window._drain()
        self.assertEqual(self.window.selected, "gemini")
        self.assertEqual(self.window.provider_combo.current(), 0)
        self.assertIn("Falta la clave de OpenAI", self.speech.speak.call_args.args[0])

    def test_advanced_mode_starts_off_and_turns_off_on_gemini(self):
        self.assertFalse(self.window.advanced_mode)
        self.window.providers["openai"] = Mock()
        self.window._set_provider("openai")
        self.window.settings = replace(self.window.settings, advanced_mode=True)
        self.window._set_provider("openai")
        self.window._set_provider("gemini")
        self.assertFalse(self.window.advanced_mode)
        self.assertIn("Modo avanzado de Luna desactivado", self.speech.speak.call_args.args[0])
        self.window._set_provider("openai")
        self.assertTrue(self.window.advanced_mode)

    def test_review_countdown_only_starts_after_reading_and_cancel_removes_it(self):
        answer, decided = [], Event()
        self.window._review_voice("Texto reconocido", answer, decided)
        self.assertIsNone(self.window.review_timer)
        self.window.events.put(("review_read", decided))
        self.window._drain()
        self.assertIsNotNone(self.window.review_timer)
        self.window._cancel()
        self.assertEqual(answer, ["cancel"])
        self.assertTrue(decided.is_set())
        self.assertIsNone(self.window.review_dialog)

    def test_blocked_visual_request_never_constructs_driver(self):
        self.window.selected = "openai"
        prepared = Prepared(AIReply(type="action", action="computer_control", spoken_response="Revisaré."), Decision(Level.BLOCKED, "Bloqueado"), 42)
        self.window.service.execute.return_value = "Bloqueado"
        with patch("ui.main_window.ComputerDriver") as driver:
            self.window._execute(prepared, "Haz clic")
        driver.assert_not_called()

    def test_visual_session_uses_preference_immediately(self):
        self.window.selected = "openai"
        self.window.service.history = []
        self.window._apply_preferences("provider", "piper", False)
        prepared = Prepared(AIReply(type="action", action="computer_control", spoken_response="Revisaré."), Decision(Level.SAFE), 42)
        with patch("ui.main_window.ComputerDriver"), patch("ui.main_window.ComputerSession") as session:
            self.window._execute(prepared, "Haz clic")
        self.assertIsNone(session.call_args.args[3])
        self.assertFalse(self.window.service.security.require_confirmation)

    def test_cancel_hotkey_sets_event_without_waiting_for_ui_dialog(self):
        with patch.object(self.window, "_target", return_value=42):
            self.window._hotkey_event("cancel")
        self.assertTrue(self.window.cancel_event.is_set())


if __name__ == "__main__":
    unittest.main()
