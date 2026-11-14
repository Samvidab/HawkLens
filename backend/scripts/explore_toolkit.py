"""T0.3 toolkit discovery: inventory the CoStar kit without copying anything into the repo.

Kit location: env COSTAR_KIT_DIR (backend/.env or process env), default ~/costar-kit.

Prints:
  - every file in the kit with its size
  - the head of index.md, models/commercial-property.md
  - top-level keys / property names of schemas/commercial-property.schema.json
  - CSV headers + first row for every *.csv (commercial-properties.csv, models_index.csv, ...)
  - the keys of the first JSONL record (streamed: reads one line, never the whole file)
  - a JSONL line count (streamed) unless --no-count

Usage: python scripts/explore_toolkit.py [--no-count] [--head N]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def kit_dir() -> Path:
    raw = os.environ.get("COSTAR_KIT_DIR")
    if not raw:
        try:
            from dotenv import dotenv_values

            raw = dotenv_values(BACKEND_DIR / ".env").get("COSTAR_KIT_DIR")
        except ImportError:
            raw = None
    return Path(raw or "~/costar-kit").expanduser()


def head(path: Path, n: int) -> str:
    out = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= n:
                out.append("  …")
                break
            out.append(line.rstrip("\n"))
    return "\n".join(out)


def section(title: str) -> None:
    print(f"\n{'=' * 8} {title} {'=' * 8}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-count", action="store_true")
    ap.add_argument("--head", type=int, default=60)
    ap.add_argument("--pull", type=int, metavar="PROPERTY_ID", help="run the T0.3 sample pulls for one property")
    args = ap.parse_args()

    root = kit_dir()
    section(f"kit: {root}")
    files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []
    if not files:
        print("NO FILES FOUND — kit missing or extraction incomplete.")
        return 1
    for p in files:
        print(f"{p.stat().st_size:>14,}  {p.relative_to(root)}")

    for rel in ("index.md", "models/commercial-property.md"):
        p = root / rel
        section(rel)
        print(head(p, args.head) if p.exists() else "(missing)")

    schema = root / "schemas/commercial-property.schema.json"
    section(schema.name)
    if schema.exists():
        s = json.loads(schema.read_text())
        print("top-level keys:", list(s))
        props = s.get("properties", {})
        print(f"{len(props)} properties; required: {s.get('required')}")
        for name, spec in props.items():
            t = spec.get("type") or spec.get("$ref") or spec.get("anyOf")
            print(f"  {name}: {t} — {str(spec.get('description', ''))[:80]}")
    else:
        print("(missing)")

    for p in [f for f in files if f.suffix == ".csv"]:
        section(str(p.relative_to(root)))
        with p.open(newline="", encoding="utf-8", errors="replace") as f:
            r = csv.reader(f)
            print("header:", next(r, None))
            print("row 1: ", next(r, None))

    for p in [f for f in files if f.suffix == ".jsonl"]:
        section(str(p.relative_to(root)))
        with p.open(encoding="utf-8") as f:
            first = json.loads(f.readline())
            print("keys of record 1:", list(first) if isinstance(first, dict) else type(first))
            if not args.no_count:
                print("records:", 1 + sum(1 for _ in f))

    if args.pull:
        import asyncio

        asyncio.run(sample_pulls(root, args.pull))
    return 0


AERIAL = 1  # AttachmentType2.Aerial
MATTERPORT_REF_TYPES = {36, 234}  # ExternalReferenceType2: MatterportScan, MatterportStreamingKey


async def sample_pulls(root: Path, property_id: int) -> None:
    """T0.3 sample pulls, every one through adapters/cache.py."""
    sys.path.insert(0, str(BACKEND_DIR))
    import httpx

    from app.adapters.cache import cached, cached_bytes

    section(f"sample pulls for PropertyId {property_id}")

    def find_record() -> dict:
        with (root / "data/commercial-property.jsonl").open(encoding="utf-8") as f:
            for line in f:  # streamed; only lines whose head names this id are parsed
                head = line[:40].replace(" ", "")
                if f'"id":{property_id},' in head:
                    rec = json.loads(line)
                    if rec.get("id") == property_id:
                        return rec
        raise KeyError(property_id)

    rec = await cached("costar.property", {"property_id": property_id}, find_record)
    pa = rec.get("primaryAddress") or {}
    print("1) CoStar record:", rec.get("buildingName"), "|", pa.get("latitude"), pa.get("longitude"),
          "| type", rec.get("propertyType"), "| RBA", rec.get("rentableBuildingAreaSquareFeet"),
          "| stories", rec.get("numStoriesAboveGrade"))

    def csv_models() -> list[str]:
        with (root / "commercial-properties.csv").open(newline="") as f:
            return [r["MatterportModelId"] for r in csv.DictReader(f)
                    if r["PropertyId"] == str(property_id) and r["MatterportModelId"]]

    models = await cached("costar.matterport_models", {"property_id": property_id}, csv_models)
    in_record = sorted({a["videoKey"] for a in rec.get("attachments") or []
                        if a.get("videoExternalReferenceType") in MATTERPORT_REF_TYPES and a.get("videoKey")})
    print(f"2) Matterport models (csv): {models}")
    print(f"   Matterport videoKeys in record attachments: {in_record}  match={sorted(models) == in_record}")

    aerials = [a for a in rec.get("attachments") or [] if a.get("attachmentType") == AERIAL and a.get("attachmentUri")]
    print(f"3) CoStar aerial photo attachments: {len(aerials)}")
    if aerials:
        a = aerials[0]

        async def fetch() -> bytes:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
                r = await c.get(a["attachmentUri"])
                r.raise_for_status()
                return r.content

        try:
            path = await cached_bytes("costar.attachment", {"attachment_id": a["attachmentMasterId"], "size": 112},
                                      fetch, ext=".jpg")
            print(f"   saved {path} ({path.stat().st_size:,} bytes) caption={a.get('caption')!r}")
        except Exception as e:  # report and keep going; CDN currently returns 403
            print(f"   FAILED: {type(e).__name__}: {str(e).splitlines()[0]}")
    print("4) Vexcel overhead/oblique: NOT AVAILABLE (no Vexcel docs/endpoints in the kit)")


if __name__ == "__main__":
    sys.exit(main())
