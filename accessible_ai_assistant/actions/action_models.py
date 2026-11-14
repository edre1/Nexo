"""Strict boundary for model output. Unknown actions or parameters are rejected."""
from typing import Literal, get_args
from pydantic import BaseModel, ConfigDict, Field, model_validator

from utils.spoken_text import plain_spoken_text


ActionName = Literal[
    "open_application", "close_application", "get_active_window",
    "list_visible_controls", "focus_control", "write_text", "press_key",
    "save_file", "get_screen_description", "get_current_focus",
    "read_selected_text", "volume_up", "volume_down", "mute_volume",
    "computer_control", "click_control",
]


class AIReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["action", "response"]
    action: ActionName | None = None
    parameters: dict[str, str] = Field(default_factory=dict)
    spoken_response: str = Field(min_length=1, max_length=700)

    @model_validator(mode="before")
    @classmethod
    def fill_spoken_response(cls, data):
        if isinstance(data, dict) and isinstance(data.get("spoken_response"), str):
            data = dict(data)
            data["spoken_response"] = plain_spoken_text(data["spoken_response"])
            if not data["spoken_response"] and data.get("type") == "action" and data.get("action") in get_args(ActionName):
                data["spoken_response"] = (
                    "Voy a revisar la ventana para realizar tu petición."
                    if data["action"] == "computer_control" else "Voy a realizar la acción solicitada."
                )
        return data

    @model_validator(mode="after")
    def valid_shape(self):
        if self.type == "action" and self.action is None:
            raise ValueError("Una acción necesita un nombre.")
        if self.type == "response" and (self.action is not None or self.parameters):
            raise ValueError("Una respuesta no puede ejecutar una acción.")
        return self
