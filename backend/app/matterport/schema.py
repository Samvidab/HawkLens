"""GraphQL introspection: discover exactly what our token can access.

Saves the raw introspection result and generates a human-readable capability report,
including whether Property Intelligence (floors/rooms/dimensions/vector floorplan) is
available. We never guess schema field names elsewhere; they come from here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.matterport.client import MatterportClient

# Minimal-but-complete introspection query (types, fields, args, enums).
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args { name type { ...TypeRef } }
        type { ...TypeRef }
      }
      inputFields { name type { ...TypeRef } }
      enumValues(includeDeprecated: true) { name }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name } } }
}
"""

# Heuristic name fragments that indicate Property Intelligence capabilities.
PI_HINTS = ("dimension", "floor", "room", "floorplan", "vector", "area", "label")


def _data_dir() -> Path:
    return get_settings().data_dir / "matterport"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


async def run_introspection(client: MatterportClient | None = None) -> dict[str, Any]:
    """Run introspection, save schema.json, and return the parsed schema dict."""
    own = client is None
    client = client or MatterportClient()
    try:
        data = await client.graphql(INTROSPECTION_QUERY, {}, op_name="introspection")
    finally:
        if own:
            await client.aclose()

    schema_path = _data_dir() / "schema.json"
    _atomic_write(schema_path, json.dumps(data, indent=2, sort_keys=True))
    return data


def _type_name(type_ref: dict[str, Any] | None) -> str:
    """Flatten a GraphQL TypeRef (NON_NULL/LIST wrappers) to a readable name."""
    if not type_ref:
        return "?"
    kind = type_ref.get("kind")
    name = type_ref.get("name")
    inner = type_ref.get("ofType")
    if kind == "NON_NULL":
        return f"{_type_name(inner)}!"
    if kind == "LIST":
        return f"[{_type_name(inner)}]"
    return name or "?"


def build_report(schema: dict[str, Any]) -> tuple[str, bool]:
    """Return (markdown_report, pi_available) from an introspection result."""
    s = schema["__schema"]
    types = {t["name"]: t for t in s["types"] if t.get("name")}
    query_root = s["queryType"]["name"]
    root = types.get(query_root, {})

    lines: list[str] = ["# Matterport schema capability report", ""]
    lines.append(f"- Query root: `{query_root}`")
    mutation = s.get("mutationType")
    lines.append(f"- Mutation root: `{mutation['name'] if mutation else 'none'}`")
    lines.append(f"- Total types exposed: {len(types)}")
    lines.append("")

    # Query root fields (entry points).
    lines.append("## Query root fields")
    for f in root.get("fields") or []:
        args = ", ".join(f"{a['name']}: {_type_name(a['type'])}" for a in (f.get("args") or []))
        lines.append(f"- `{f['name']}({args}) -> {_type_name(f['type'])}`")
    lines.append("")

    # Pagination fields anywhere (nextOffset / totalResults).
    paginated = [
        name
        for name, t in types.items()
        if {fld["name"] for fld in (t.get("fields") or [])} & {"nextOffset", "totalResults", "results"}
    ]
    lines.append("## Types with pagination fields (results / nextOffset / totalResults)")
    lines += [f"- `{name}`" for name in sorted(paginated)] or ["- (none found)"]
    lines.append("")

    # The Model type fields.
    model = types.get("Model")
    lines.append("## `Model` type fields")
    if model and model.get("fields"):
        for f in model["fields"]:
            lines.append(f"- `{f['name']}: {_type_name(f['type'])}`")
    else:
        lines.append("- (no `Model` type found — check the query root fields above)")
    lines.append("")

    # Property Intelligence detection.
    pi_types = sorted(
        name for name in types if any(h in name.lower() for h in PI_HINTS)
    )
    pi_available = len(pi_types) > 0
    lines.append("## Property Intelligence availability")
    lines.append(f"- pi_available (heuristic): **{pi_available}**")
    lines.append("- Matching types:")
    lines += [f"  - `{name}`" for name in pi_types] or ["  - (none)"]
    lines.append("")
    lines.append(
        "> Heuristic only — names containing: "
        + ", ".join(PI_HINTS)
        + ". Confirm against the Model fields above before building PI ingestion."
    )
    lines.append("")

    return "\n".join(lines), pi_available


async def introspect_and_report(client: MatterportClient | None = None) -> tuple[str, bool]:
    """Run introspection, write schema.json + schema-report.md, return (report, pi_available)."""
    schema = await run_introspection(client)
    report, pi_available = build_report(schema)
    _atomic_write(_data_dir() / "schema-report.md", report)
    return report, pi_available
