from typing import Literal

from pydantic import BaseModel


class Goal(BaseModel):
    city: Literal["Houston", "Los Angeles"]
    building_ids: list[str] | None = None
    target_pct: float
    budget_usd: float | None = None
    risk_lambda: float = 0.5
    discount_rate: float = 0.07


class OwnerAction(BaseModel):
    run_id: str
    type: Literal[
        "goal", "exclude_building", "include_building", "toggle_upgrade", "select_bar",
        "set_target", "set_budget", "set_risk", "include_unverified", "approve", "open_building",
    ]
    payload: dict = {}
