"""Pydantic models shared across agents, data/ files, and the API (TRD §5, App Flow §4)."""
from app.schemas.aerial import AerialFindings, FacadeFinding
from app.schemas.claims import Claim, Mark
from app.schemas.events import ActivityEvent
from app.schemas.goal import Goal, OwnerAction
from app.schemas.interior import InteriorFindings, Pin
from app.schemas.layout import Layout, WidgetSpec
from app.schemas.profile import BuildingProfile
from app.schemas.upgrades import FeasibleUpgrade

__all__ = [
    "ActivityEvent", "AerialFindings", "BuildingProfile", "Claim", "FacadeFinding",
    "FeasibleUpgrade", "Goal", "InteriorFindings", "Layout", "Mark", "OwnerAction",
    "Pin", "WidgetSpec",
]
