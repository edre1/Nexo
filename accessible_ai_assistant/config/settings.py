"""Load portable configuration, with secrets kept outside source files."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from config.paths import DATA_ROOT, RESOURCE_ROOT


@dataclass(frozen=True)
class Settings:
    ai_provider: str
    model: str
    openai_model: str
    hotkey_listen: str
    hotkey_cancel: str
    require_confirmation_for_sensitive_actions: bool
    enable_screen_vision: bool
    learning_mode: bool
    language: str
    microphone_max_seconds: int
    api_key: str
    openai_api_key: str


def load_settings() -> Settings:
    load_dotenv(DATA_ROOT / ".env", override=False)
    data = json.loads((RESOURCE_ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    preferences = DATA_ROOT / "preferences.json"
    if preferences.exists():
        data.update(json.loads(preferences.read_text(encoding="utf-8")))
    selected = str(data.get("ai_provider", "gemini"))
    if selected not in {"gemini", "openai"}:
        selected = "gemini"
    return Settings(
        ai_provider=selected,
        model=str(data.get("model", "gemini-3.5-flash-lite")),
        openai_model="gpt-6-luna",
        hotkey_listen=str(data.get("hotkey_listen", "Ctrl+Alt+A")),
        hotkey_cancel=str(data.get("hotkey_cancel", "Ctrl+Alt+Escape")),
        require_confirmation_for_sensitive_actions=bool(data.get("require_confirmation_for_sensitive_actions", True)),
        enable_screen_vision=bool(data.get("enable_screen_vision", True)),
        learning_mode=bool(data.get("learning_mode", True)),
        language=str(data.get("language", "es-MX")),
        microphone_max_seconds=max(3, min(30, int(data.get("microphone_max_seconds", 10)))),
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
    )


def save_listen_hotkey(value: str) -> None:
    from windows.hotkeys import parse_hotkey
    parse_hotkey(value)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    path = DATA_ROOT / "preferences.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data["hotkey_listen"] = value
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)
