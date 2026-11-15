from pathlib import Path
import re

root = Path(__file__).resolve().parents[2] if (Path(__file__).resolve().parents[2] / 'backend/app/documents/routes.py').exists() else Path.cwd()
routes = root / 'backend/app/documents/routes.py'
memo = root / 'backend/app/agents/memo.py'
if not routes.exists() or not memo.exists():
    raise SystemExit('Run this from the HawkLens project root: python apply_memo_patch.py')

source = routes.read_text()
if 'HAWKLENS_POLISHED_PDF_V1' not in source:
    start = source.find('    try:\n        from reportlab.platypus import SimpleDocTemplate')
    if start == -1:
        raise SystemExit('PDF route structure differs; no files changed. Please share backend/app/documents/routes.py')
    source = source[:start] + '''    # HAWKLENS_POLISHED_PDF_V1
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
            HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from xml.sax.saxutils import escape
    except ImportError as exc:
        raise HTTPException(503, "PDF support requires reportlab") from exc

    def build():
        buf = io.BytesIO()
        navy = colors.HexColor("#183047")
        green = colors.HexColor("#335D45")
        muted = colors.HexColor("#5D6B78")
        pale = colors.HexColor("#F2F5F3")
        doc = SimpleDocTemplate(
            buf, pagesize=letter, leftMargin=43, rightMargin=43,
            topMargin=51, bottomMargin=48,
            title="Hawk Lens | Investment Memo",
            author="Hawk Lens",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="HLTitle", parent=styles["Title"], fontName="Helvetica-Bold",
            fontSize=19, leading=23, textColor=navy, spaceAfter=9,
        ))
        styles.add(ParagraphStyle(
            name="HLSub", parent=styles["Normal"], fontSize=9,
            leading=13, textColor=muted, spaceAfter=11,
        ))
        styles.add(ParagraphStyle(
            name="HLBody", parent=styles["BodyText"], fontSize=9.5,
            leading=15, spaceAfter=10, textColor=navy,
        ))
        styles.add(ParagraphStyle(
            name="HLHeading", parent=styles["Heading2"], fontSize=12,
            leading=16, spaceBefore=14, spaceAfter=8, textColor=green,
        ))
        styles.add(ParagraphStyle(
            name="HLCell", parent=styles["Normal"], fontSize=7.1,
            leading=10, textColor=navy,
        ))
        styles.add(ParagraphStyle(
            name="HLHeaderCell", parent=styles["HLCell"], fontName="Helvetica-Bold",
            textColor=colors.white,
        ))
        styles.add(ParagraphStyle(
            name="HLDisclaimer", parent=styles["Normal"], fontSize=8,
            leading=12, textColor=muted,
        ))

        def para(text, style="HLBody"):
            return Paragraph(escape(text).replace("**", ""), styles[style])

        story = [
            para("HAWK LENS  /  INVESTMENT RESEARCH", "HLSub"),
            para("Retrofit investment memo", "HLTitle"),
            para("Plan " + plan_id + "  |  Draft for owner review", "HLSub"),
            HRFlowable(width="100%", thickness=1, color=green, spaceAfter=14),
        ]
        lines = path.read_text(encoding="utf-8").splitlines()
        table_rows = []

        def flush_table():
            if not table_rows:
                return
            parsed = []
            for raw in table_rows:
                cells = [x.strip() for x in raw.strip().strip("|").split("|")]
                if cells and all(re.fullmatch(r":?-{3,}:?", x) for x in cells):
                    continue
                parsed.append(cells)
            table_rows.clear()
            if not parsed:
                return
            count = max(len(r) for r in parsed)
            widths = ([132, 100, 96, 89, 79] if count == 5 else
                      [(letter[0] - 86) / count] * count)
            if count != 5:
                widths = [(letter[0] - 86) / count] * count
            rows = []
            for i, cells in enumerate(parsed):
                rows.append([para(cells[j] if j < len(cells) else "",
                                  "HLHeaderCell" if i == 0 else "HLCell")
                             for j in range(count)])
            t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, green),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#DEE5E2")),
            ]))
            story.append(t)
            story.append(Spacer(1, 12))

        for line in lines:
            if line.startswith("|"):
                table_rows.append(line)
                continue
            flush_table()
            if not line.strip():
                continue
            if line.startswith("# "):
                # The document already has a branded title above.
                continue
            if line.startswith("## "):
                story.append(para(line[3:], "HLHeading"))
            elif line.startswith("_") and line.endswith("_"):
                story.append(para(line.strip("_"), "HLDisclaimer"))
            else:
                story.append(para(line))
        flush_table()
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CDD7D2")))
        story.append(Spacer(1, 8))
        story.append(para(
            "Investment estimates are model outputs, not guaranteed returns. "
            "Confirm pricing, assumptions, and evidence verification before investment decisions.",
            "HLDisclaimer",
        ))

        def page_footer(canvas, document):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#D8E0DC"))
            canvas.line(43, 36, letter[0] - 43, 36)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(muted)
            canvas.drawString(43, 24, "HAWK LENS  |  INVESTMENT MEMO")
            canvas.drawRightString(letter[0] - 43, 24, f"Page {document.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
        return buf.getvalue()

    pdf = await run_in_threadpool(build)
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="hawklens-investment-memo-{plan_id}.pdf"'},
    )
'''
    routes.write_text(source)
    print('Updated:', routes)
else:
    print('PDF formatting patch already applied')

source = memo.read_text()
old = '"The probability of hitting the target is {{p_hit_target}}. Every upgrade is backed by images the agents inspected "\n    "and checked."'
new = '"The probability of hitting the target is {{p_hit_target}}. "\n    "Evidence and verification status should be reviewed for each upgrade before approval."'
if old in source:
    memo.write_text(source.replace(old, new))
    print('Corrected unsupported evidence claim in:', memo)
elif 'Evidence and verification status should be reviewed' in source:
    print('Evidence disclaimer already patched')
else:
    print('NOTICE: Could not locate the fallback claim; check backend/app/agents/memo.py manually')
print('Done. Restart FastAPI and regenerate the memo to update its text.')
