"""Read-only count/peek: how many models can our token see, how many in Houston,
and a sample model's thumbnail + Showcase embed URL. No ingestion, no writes to data/.

Usage (from backend/):  python -m scripts.mp_count_peek
"""
from __future__ import annotations

import asyncio
import sys

from app.matterport.client import MatterportAuthError, MatterportClient

# Count only: ask for 1 result but read totalResults.
COUNT_QUERY = """
query Count($query: String, $pageSize: Int) {
  models(query: $query, pageSize: $pageSize) {
    totalResults
    nextOffset
    results { id }
  }
}
"""

# Peek list: fields available on the SEARCH result (thumbnail + address + published).
PEEK_QUERY = """
query Peek($query: String, $pageSize: Int) {
  models(query: $query, pageSize: $pageSize) {
    totalResults
    results {
      id
      name
      created
      address { locality administrativeArea postalCode countryCode address }
      geolocation { lat long }
      image { url }
      publication { published }
    }
  }
}
"""

# The interactive-tour embed URL lives on the FULL model(id), not the search result.
MODEL_EMBED_QUERY = """
query ModelEmbed($id: ID!) {
  model(id: $id) {
    id
    name
    image { url }
    publication { embed url published }
  }
}
"""


async def _main() -> int:
    try:
        async with MatterportClient() as c:
            all_models = await c.graphql(COUNT_QUERY, {"query": None, "pageSize": 1}, op_name="count_all")
            houston = await c.graphql(PEEK_QUERY, {"query": "Houston", "pageSize": 5}, op_name="peek_houston")
    except MatterportAuthError as exc:
        print(f"AUTH ERROR: {exc}", file=sys.stderr)
        return 2

    total_all = all_models["models"]["totalResults"]
    conn = houston["models"]
    total_houston_q = conn["totalResults"]
    results = conn["results"]

    print("=== Matterport account count / peek ===")
    print(f"Total models visible to this token: {total_all}")
    print(f"Models returned for query='Houston':  {total_houston_q}")
    print()

    # Verify how many of the returned sample actually have locality == Houston.
    def city(m):
        a = m.get("address") or {}
        return (a.get("locality") or "").strip()

    houston_cities = {}
    print(f"Sample of up to 5 'Houston' query results:")
    for m in results:
        has_thumb = bool((m.get("image") or {}).get("url"))
        pub = m.get("publication") or {}
        published = pub.get("published")
        c_name = city(m)
        houston_cities[c_name] = houston_cities.get(c_name, 0) + 1
        print(
            f"  - {m['id']}  city={c_name!r}  name={m.get('name')!r}  "
            f"thumbnail={has_thumb}  published={published}"
        )

    # Peek one full model to confirm the interactive embed URL is available.
    if results:
        sample_id = results[0]["id"]
        async with MatterportClient() as c:
            em = await c.graphql(MODEL_EMBED_QUERY, {"id": sample_id}, op_name=f"embed_{sample_id}")
        fm = em["model"]
        pub = fm.get("publication") or {}
        embed = pub.get("embed") or ""
        print()
        print(f"Full model(id) peek for {sample_id}:")
        print(f"  name:      {fm.get('name')!r}")
        print(f"  thumbnail: {(fm.get('image') or {}).get('url')}")
        print(f"  published: {pub.get('published')}")
        print(f"  embed URL: {embed[:120]}{'…' if len(embed) > 120 else ''}")
        print(f"  show URL:  {pub.get('url')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
