// The demo portfolio's buildings (GET /portfolio on the VITE_API_URL backend) in the shape the building cards, the ⌘K
// search and ShowcaseModal already use: { id (the Matterport model whose tour is shown), name, address, thumbnail_url,
// show_url }. Only these buildings are listed; every other stored Matterport tour is hidden. Card images come from the
// stored Matterport record of the same model when there is one; nothing else is filled in.
import { fetchProperties } from './api'

/** Pure: one card per portfolio building that has a Matterport model; `stored` = the /properties records (for images). */
export function portfolioCards(buildings, stored = []) {
  const byId = new Map((stored || []).map((p) => [p.id, p]))
  return (buildings || [])
    .filter((b) => b && b.matterport_model_id)
    .map((b) => {
      const p = byId.get(b.matterport_model_id) || {}
      return {
        id: b.matterport_model_id,
        building_id: b.building_id,
        name: b.name ?? p.name ?? null,
        address: b.address ?? p.address ?? null,
        city: b.city ?? p.city ?? null,
        thumbnail_url: p.thumbnail_url ?? null,
        show_url: b.showcase_url ?? p.show_url ?? null,
      }
    })
}

/** Same result shape as fetchProperties ({ results }), so pages swap one call. */
export async function fetchPortfolioProperties() {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const res = await fetch(`${base}/portfolio`)
  if (!res.ok) throw new Error(`portfolio ${res.status}`)
  const portfolio = await res.json()
  const stored = await fetchProperties({ limit: 500 }).then((d) => d.results || []).catch(() => [])
  const results = portfolioCards(portfolio.buildings, stored)
  return { total: results.length, results }
}
