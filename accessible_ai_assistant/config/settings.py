"""Load portable configuration, with secrets kept outside source files."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from config.paths import DATA_ROOT, RESOURCE_ROOT
from windows.hotkeys import DEFAULT_PROVIDER_SHORTCUT, parse_hotkey


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
    speech_recognition: str = "provider"
    speech_output: str = "piper"
    hotkey_provider: str = DEFAULT_PROVIDER_SHORTCUT
    advanced_mode: bool = False
    review_transcript: bool = False
    speak_review_hint: bool = True
    gemini_web_search: bool = False
    hotkey_repeat: str = "Ctrl+Alt+R"
    hotkey_text: str = "Ctrl+Alt+T"
    luna_seconds: int = 240
    luna_turns: int = 12
    luna_actions: int = 40
    shell_seconds: int = 45



def load_settings() -> Settings:
    load_dotenv(DATA_ROOT / ".env", override=False)
    data = json.loads((RESOURCE_ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    preferences = DATA_ROOT / "preferences.json"
    if preferences.exists():
        data.update(json.loads(preferences.read_text(encoding="utf-8")))
    selected = str(data.get("ai_provider", "openai"))
    if selected not in {"gemini", "openai"}:
        selected = "openai"
    return Settings(
        ai_provider=selected,
        hotkey_repeat=str(data.get("hotkey_repeat", "Ctrl+Alt+R")),
        hotkey_text=str(data.get("hotkey_text", "Ctrl+Alt+T")),
        luna_seconds=int(data.get("luna_seconds", 240)),
        luna_turns=int(data.get("luna_turns", 12)),
        luna_actions=int(data.get("luna_actions", 40)),
        shell_seconds=int(data.get("shell_seconds", 45)),

        model=str(data.get("model", "gemini-3.5-flash-lite")),
        openai_model="gpt-6-luna",
        hotkey_listen=str(data.get("hotkey_listen", "Ctrl+Alt+A")),
        hotkey_cancel=str(data.get("hotkey_cancel", "Ctrl+Alt+Escape")),
        hotkey_provider=str(data.get("hotkey_provider", DEFAULT_PROVIDER_SHORTCUT)),
        advanced_mode=data.get("advanced_mode") is True,
        review_transcript=data.get("review_transcript") is True,
        speak_review_hint=data.get("speak_review_hint", True) is True,
        gemini_web_search=data.get("gemini_web_search") is True,
        require_confirmation_for_sensitive_actions=bool(data.get("require_confirmation_for_sensitive_actions", True)),
        enable_screen_vision=bool(data.get("enable_screen_vision", True)),
        learning_mode=bool(data.get("learning_mode", True)),
        language=str(data.get("language", "es-MX")),
        microphone_max_seconds=60,
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        speech_recognition="provider",
        speech_output="windows" if data.get("speech_output") == "windows" else "piper",
    )


def save_listen_hotkey(
    value: str, recognition: str | None = None, voice: str | None = None, *,
    confirm_actions: bool | None = None,
    hotkey_provider: str | None = None,
    advanced_mode: bool | None = None,
    review_transcript: bool | None = None,
    speak_review_hint: bool | None = None,
    gemini_web_search: bool | None = None,
    extras: dict | None = None,
) -> None:
    parse_hotkey(value)
    if hotkey_provider is not None:
        parse_hotkey(hotkey_provider)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    path = DATA_ROOT / "preferences.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data["hotkey_listen"] = value
    if hotkey_provider is not None:
        data["hotkey_provider"] = hotkey_provider
    data["speech_recognition"] = "provider"
    if voice in {"piper", "windows"}:
        data["speech_output"] = voice
    if confirm_actions is not None:
        data["require_confirmation_for_sensitive_actions"] = confirm_actions
    if advanced_mode is not None:
        data["advanced_mode"] = advanced_mode
    if review_transcript is not None:
        data["review_transcript"] = review_transcript
    if speak_review_hint is not None:
        data["speak_review_hint"] = speak_review_hint
    if gemini_web_search is not None:
        data["gemini_web_search"] = gemini_web_search
    if extras:
        data.update(extras)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)
