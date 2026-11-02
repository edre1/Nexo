"""Strict boundary for model output. Unknown actions or parameters are rejected."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


ActionName = Literal[
    "open_application", "close_application", "get_active_window",
    "list_visible_controls", "focus_control", "write_text", "press_key",
    "save_file", "get_screen_description", "get_current_focus",
    "read_selected_text", "volume_up", "volume_down", "mute_volume",
    "move_cursor", "click_control",
]


class AIReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["action", "response"]
    action: ActionName | None = None
    parameters: dict[str, str] = Field(default_factory=dict)
    spoken_response: str = Field(min_length=1, max_length=700)

    @model_validator(mode="after")
    def valid_shape(self):
        if self.type == "action" and self.action is None:
            raise ValueError("Una acción necesita un nombre.")
        if self.type == "response" and (self.action is not None or self.parameters):
            raise ValueError("Una respuesta no puede ejecutar una acción.")
        return self
