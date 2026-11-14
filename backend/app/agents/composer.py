"""UI composer v0: always the portfolio_overview template, props filled by the resolver.

(v1, T3.2, will detect situations and let Gemini reorder/annotate within limits.)
A widget whose data is not ready is dropped with an `error` event rather than blanking the page.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import events
from app.schemas.layout import Layout, Situation
from app.storage import data_path, write_json
from app.widgets.resolver import ResolveContext, ResolveError, resolve_layout, resolve_widget
from app.widgets.registry import RegistryError
from app.widgets.templates import template_for


def compose_v0(run_id: str, *, focus_building_id: str | None = None) -> Layout:
    situation: Situation = "portfolio_overview"
    ctx = ResolveContext.load(data_path(), run_id, focus_building_id=focus_building_id, situation=situation)
    kept = []
    for spec in template_for(situation):
        try:
            resolve_widget(spec, ctx)
            kept.append(spec)
        except (ResolveError, RegistryError) as e:
            events.emit(run_id, "Composer", "error", f"dropped {spec.type}: {str(e)[:60]}")
    layout = resolve_layout(ctx, situation, kept)
    write_json(data_path("layout.json"), layout)
    events.emit(run_id, "Composer", "compose", f"showing {situation.replace('_', ' ')}, {len(layout.widgets)} widgets")
    return layout


def save_state(run_id: str, layout: Layout, goal: dict | None, plan_id: str | None) -> dict:
    state = {"run_id": run_id, "goal": goal, "plan_id": plan_id, "layout": layout.model_dump(mode="json"),
             "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write_json(data_path("runs", run_id, "state.json"), state)
    return state
