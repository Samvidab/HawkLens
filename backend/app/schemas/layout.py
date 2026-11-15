"""Layout JSON contract (App Flow §4). Props are filled by the resolver, never by an LLM."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Situation = Literal["portfolio_overview", "building_detail", "target_gap", "verification_issue", "approved"]
Size = Literal["full", "wide", "half", "side"]
GRID_COLUMNS = {"full": 12, "wide": 8, "half": 6, "side": 4}
MAX_WIDGETS = 8
MAX_WHY = 90


class WidgetSpec(BaseModel):
    id: str
    type: str  # must be a key of widgets.registry.WIDGETS (checked by registry.validate_layout)
    title: str
    why: str = Field(max_length=MAX_WHY)
    size: Size
    data_ref: str | None = None
    props: dict = {}


class Layout(BaseModel):
    layout_id: str
    run_id: str
    situation: Situation
    focus_building_id: str | None = None
    generated_at: str
    widgets: list[WidgetSpec] = Field(max_length=MAX_WIDGETS)

    @model_validator(mode="after")
    def _feed_present(self) -> "Layout":
        feeds = [w for w in self.widgets if w.type == "activity_feed"]
        if len(feeds) != 1 or feeds[0].size != "side":
            raise ValueError("layout must include exactly one activity_feed widget with size 'side'")
        return self
