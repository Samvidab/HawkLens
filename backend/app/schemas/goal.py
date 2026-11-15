from typing import Literal

from pydantic import BaseModel, Field


class Goal(BaseModel):
    city: Literal["Houston", "Los Angeles"]
    building_ids: list[str] | None = None
    target_pct: float = Field(ge=0, le=100)
    budget_usd: float | None = Field(default=None, ge=0)
    risk_lambda: float = Field(default=0.5, ge=0)
    discount_rate: float = Field(default=0.07, ge=0, le=1)


class OwnerAction(BaseModel):
    run_id: str
    type: Literal[
        "goal", "exclude_building", "include_building", "toggle_upgrade", "select_bar",
        "set_target", "set_budget", "set_risk", "include_unverified", "approve", "open_building",
    ]
    payload: dict = {}
