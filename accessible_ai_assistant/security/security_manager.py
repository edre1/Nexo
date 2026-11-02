"""Central policy: no model supplied command, path or executable reaches Windows."""
from dataclasses import dataclass
from actions.action_models import AIReply
from actions.action_registry import ALLOWED_KEYS, APPLICATIONS, CATALOG, CLICK_NAMES, CURSOR_DIRECTIONS, Level


DENIED = "Esta acción no está permitida por seguridad."


@dataclass(frozen=True)
class Decision:
    level: Level
    reason: str = ""


class SecurityManager:
    def __init__(self, require_confirmation: bool = True):
        self.require_confirmation = require_confirmation

    def evaluate(self, reply: AIReply, target_title: str = "", focused_control: str = "") -> Decision:
        if reply.type != "action" or reply.action not in CATALOG:
            return Decision(Level.BLOCKED, DENIED)
        spec = CATALOG[reply.action]
        keys = frozenset(reply.parameters)
        if not spec.required <= keys or not keys <= spec.required | spec.optional:
            return Decision(Level.BLOCKED, DENIED)
        if any(len(value) > 2000 for value in reply.parameters.values()):
            return Decision(Level.BLOCKED, DENIED)
        if reply.action == "open_application":
            app = reply.parameters["application"].strip().lower()
            if not any(app in aliases for aliases in APPLICATIONS.values()):
                return Decision(Level.BLOCKED, DENIED)
        if reply.action == "press_key":
            key = reply.parameters["key"].upper().replace("CONTROL", "CTRL").replace(" ", "")
            if key not in ALLOWED_KEYS:
                return Decision(Level.BLOCKED, DENIED)
        if reply.action == "write_text" and not reply.parameters["text"]:
            return Decision(Level.BLOCKED, DENIED)
        if reply.action == "focus_control" and not reply.parameters["name"].strip():
            return Decision(Level.BLOCKED, DENIED)
        if reply.action == "move_cursor":
            direction = reply.parameters["direction"].strip().lower()
            count = reply.parameters.get("count", "1").strip()
            if direction not in CURSOR_DIRECTIONS or not count.isdecimal() or not 1 <= int(count) <= 20:
                return Decision(Level.BLOCKED, DENIED)
            if direction in {"home", "end", "document_start", "document_end"} and count != "1":
                return Decision(Level.BLOCKED, DENIED)
        if reply.action == "click_control":
            if reply.parameters["name"].strip().casefold() not in CLICK_NAMES:
                return Decision(Level.BLOCKED, DENIED)
        if reply.action in {"write_text", "press_key", "save_file"}:
            destination = f"{target_title} {focused_control}".casefold()
            if any(word in destination for word in ("powershell", "command prompt", "símbolo del sistema", "cmd.exe", "terminal", "consola")):
                return Decision(Level.BLOCKED, DENIED)
        if spec.level == Level.CONFIRM and self.require_confirmation:
            return Decision(Level.CONFIRM)
        return Decision(Level.SAFE)
