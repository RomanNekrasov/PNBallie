"""Group-specific presentation; match sides remain stable identifiers."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TeamColor = Literal["orange", "blue", "red", "green", "yellow", "purple", "black", "white"]


class TableSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orange_color: TeamColor = "orange"
    blue_color: TeamColor = "blue"
    field_color: str = Field(default="#2d6a30", pattern=r"^#[0-9a-fA-F]{6}$")
    rim_color: str = Field(default="#5a3a1a", pattern=r"^#[0-9a-fA-F]{6}$")
    score_position: Literal["own_goal", "opponent_goal"] = "opponent_goal"

    @model_validator(mode="after")
    def distinct_teams(self):
        if self.orange_color == self.blue_color:
            raise ValueError("Choose different team colors")
        return self
