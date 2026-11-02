"""The only accepted action names, argument names and fixed OS targets."""
from dataclasses import dataclass
from enum import IntEnum


class Level(IntEnum):
    SAFE = 1
    CONFIRM = 2
    BLOCKED = 3


@dataclass(frozen=True)
class ActionSpec:
    level: Level
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()


CATALOG: dict[str, ActionSpec] = {
    "open_application": ActionSpec(Level.SAFE, frozenset({"application"})),
    "close_application": ActionSpec(Level.CONFIRM),
    "get_active_window": ActionSpec(Level.SAFE),
    "list_visible_controls": ActionSpec(Level.SAFE),
    "focus_control": ActionSpec(Level.SAFE, frozenset({"name"})),
    "move_cursor": ActionSpec(Level.SAFE, frozenset({"direction"}), frozenset({"count"})),
    "click_control": ActionSpec(Level.CONFIRM, frozenset({"name"})),
    "write_text": ActionSpec(Level.CONFIRM, frozenset({"text"})),
    "press_key": ActionSpec(Level.CONFIRM, frozenset({"key"})),
    "save_file": ActionSpec(Level.CONFIRM),
    "get_screen_description": ActionSpec(Level.SAFE),
    "get_current_focus": ActionSpec(Level.SAFE),
    "read_selected_text": ActionSpec(Level.SAFE),
    "volume_up": ActionSpec(Level.SAFE),
    "volume_down": ActionSpec(Level.SAFE),
    "mute_volume": ActionSpec(Level.SAFE),
}

APPLICATIONS = {
    "notepad": ("notepad", "bloc de notas"),
    "chrome": ("chrome", "google chrome"),
    "vscode": ("vscode", "visual studio code", "vs code", "code"),
    "edge": ("edge", "microsoft edge"),
    "explorer": ("explorer", "explorador de archivos"),
    "calculator": ("calculator", "calculadora", "calc"),
}

ALLOWED_KEYS = {
    "CTRL+S", "CTRL+Z", "CTRL+Y", "CTRL+C", "CTRL+V", "CTRL+A",
    "ENTER", "TAB", "SHIFT+TAB", "ESC", "UP", "DOWN", "LEFT", "RIGHT",
    "HOME", "END", "BACKSPACE", "DELETE", "F2", "F5",
}

CURSOR_DIRECTIONS = {
    "left", "right", "up", "down", "home", "end",
    "document_start", "document_end",
}

# Clicks are intentionally limited to navigation controls. Other operations
# must be added as explicit actions with their own safety rules.
CLICK_NAMES = {
    "archivo", "file", "editar", "edit", "ver", "view", "vista",
    "ayuda", "help", "atrás", "atras", "back", "adelante", "forward",
    "explorador", "explorer", "nueva pestaña",
    "new tab", "agregar nueva pestaña", "cancelar", "cancel", "volver",
}
