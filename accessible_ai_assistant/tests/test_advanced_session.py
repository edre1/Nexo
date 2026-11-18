import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ai.advanced_session import AdvancedSession
from utils.advanced_activity import AdvancedActivity


class AdvancedSessionTests(unittest.TestCase):
    def test_unsaved_editor_changes_prevent_overwriting_file(self):
        import time
        path = self.root / "example.py"
        path.write_text("print(1)", encoding="utf-8")
        snapshot = {"path": str(path), "text": "print(2)", "disk_text": "print(1)", "unsaved": True}
        self.session.editor = snapshot
        self.session.deadline = time.monotonic() + 10
        with patch("windows.editor_file.editor_snapshot", return_value=snapshot):
            with self.assertRaisesRegex(ValueError, "sin guardar"):
                self.session._write_file(path, "print(3)")
        self.assertEqual(path.read_text(encoding="utf-8"), "print(1)")

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)
        self.activity = AdvancedActivity(self.root / "activity")
        self.provider = Mock(model="gpt-6-luna")
        self.provider.reasoning_for.return_value = {"effort": "medium"}
        self.create = self.provider.client.responses.create
        self.cancel = threading.Event()
        self.driver = Mock()
        self.session = AdvancedSession(self.provider, self.driver, self.cancel, Mock(), self.activity)

    def events(self):
        return [json.loads(line) for line in (self.activity.root / "actividad.txt").read_text(encoding="utf-8").splitlines()]

    def test_tool_loop_writes_file_and_keeps_original_copy(self):
        path = self.root / "example.html"
        path.write_text("original", encoding="utf-8")
        call = {"type": "function_call", "name": "write_file", "call_id": "call_1", "arguments": json.dumps({"path": str(path), "content": "<p>nuevo</p>"})}
        item = SimpleNamespace(**call, model_dump=lambda **_: call)
        self.create.side_effect = [SimpleNamespace(status="completed", output=[item]), SimpleNamespace(status="completed", output=[], output_text="**Listo.**")]
        self.assertEqual(self.session.run("Actualiza example.html", "", "Contexto"), "Listo.")
        self.assertEqual(path.read_text(encoding="utf-8"), "<p>nuevo</p>")
        events = self.events()
        self.assertEqual([event["event"] for event in events], ["session_started", "file_write_started", "file_write_ended", "session_ended"])
        self.assertEqual(Path(events[1]["before"]["backup"]).read_text(encoding="utf-8"), "original")
        self.assertNotEqual(events[1]["before"]["sha256"], events[2]["after"]["sha256"])
        args = self.create.call_args.kwargs
        self.assertIn({"type": "web_search"}, args["tools"])
        self.assertIn({"type": "computer"}, args["tools"])
        self.assertEqual(args["input"][-1]["call_id"], "call_1")

    def test_cancelled_reply_cannot_execute_a_local_command(self):
        def cancel_after_response(**_):
            self.cancel.set()
            return SimpleNamespace(status="completed", output=[Mock(type="function_call")])
        self.create.side_effect = cancel_after_response
        with self.assertRaises(InterruptedError):
            self.session.run("Ejecuta PowerShell", "", "")
        self.assertEqual([event["event"] for event in self.events()], ["session_started", "session_ended"])

    def test_web_search_sources_remain_available_without_inline_citations(self):
        call = {"action": {"sources": [{"url": "https://www.python.org/"}]}, "status": "completed"}
        item = SimpleNamespace(type="web_search_call", model_dump=lambda **_: call)
        self.create.return_value = SimpleNamespace(status="completed", output=[item], output_text="Encontré Python.")
        self.session.run("Busca el sitio oficial de Python", "", "")
        self.assertEqual(self.session.sources, [("www.python.org", "https://www.python.org/")])
        self.assertEqual(self.events()[1]["event"], "web_search")
