"""Investment memo endpoints. No Nessie writes or financing approval."""
from __future__ import annotations

import io
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.agents.memo import write_memo
from app.storage import data_path, read_json

router = APIRouter(prefix="/documents", tags=["documents"])


def current_plan():
    plan = read_json(data_path("plans", "current.json"), {}) or {}
    if not plan.get("plan_id") or not plan.get("selected") or not (plan.get("total_upfront") or 0) > 0:
        raise HTTPException(409, "No valid retrofit plan yet. Run the building survey and pricing first.")
    return plan


def payload(plan):
    path = data_path("memo", f"{plan['plan_id']}.md")
    markdown = path.read_text(encoding="utf-8") if path.exists() else None
    selected = plan.get("selected", [])
    buildings = set()
    for d in data_path("buildings").glob("*"):
        if not d.is_dir():
            continue
        for u in read_json(d / "feasibility.json", []) or []:
            if u.get("upgrade_id") in selected:
                buildings.add(u.get("building_id", d.name))
    return {
        "plan_id": plan["plan_id"],
        "status": "ready" if markdown else "not_generated",
        "markdown": markdown,
        "metrics": {
            "total_upfront": plan.get("total_upfront"),
            "exp_npv": plan.get("exp_npv"),
            "cvar5": plan.get("cvar5"),
            "p_loss": plan.get("p_loss"),
            "p_hit_target": plan.get("p_hit_target"),
            "tonnes_per_year": plan.get("tonnes_per_year"),
            "upgrade_count": len(selected),
            "building_count": len(buildings),
        },
        "approved": plan.get("financing", {}).get("state") == "executed",
    }


@router.get("/memo")
def get_memo():
    return payload(current_plan())


class GenerateRequest(BaseModel):
    plan_id: str


@router.post("/memo/generate")
async def generate_memo(body: GenerateRequest):
    plan = current_plan()
    if body.plan_id != plan["plan_id"]:
        raise HTTPException(409, "Plan has changed. Refresh before generating.")
    await write_memo("documents", plan)
    return payload(plan)


@router.get("/memo/download")
async def download_memo(plan_id: str):
    plan = current_plan()
    if plan_id != plan["plan_id"]:
        raise HTTPException(409, "Plan has changed. Refresh before downloading.")
    path = data_path("memo", f"{plan['plan_id']}.md")
    if not path.exists():
        raise HTTPException(404, "Generate the memo first.")
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
    except ImportError as exc:
        raise HTTPException(503, "PDF support requires reportlab") from exc
    def build():
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, title="Hawk Lens Investment Memo")
        styles = getSampleStyleSheet()
        story = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                story.append(Spacer(1, 8))
            elif line.startswith("# "):
                story.append(Paragraph(escape(line[2:]), styles["Title"]))
            elif line.startswith("## "):
                story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
            elif line.startswith("|"):
                story.append(Paragraph(escape(line).replace("|", " &nbsp; | &nbsp; "), styles["BodyText"]))
            else:
                story.append(Paragraph(escape(line), styles["BodyText"]))
        doc.build(story)
        return buf.getvalue()
    pdf = await run_in_threadpool(build)
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="hawklens-investment-memo-{plan_id}.pdf"'})
