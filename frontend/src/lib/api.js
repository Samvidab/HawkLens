// Tiny client for the HawkLens backend (Matterport property data).
// Base URL can be overridden with VITE_API_BASE; defaults to the local dev backend.
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export async function fetchProperties({ q, limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const res = await fetch(`${BASE}/properties?${params.toString()}`)
  if (!res.ok) throw new Error(`properties ${res.status}`)
  return res.json()
}

export async function fetchProperty(id) {
  const res = await fetch(`${BASE}/properties/${id}`)
  if (!res.ok) throw new Error(`property ${id} ${res.status}`)
  return res.json()
}

// Resolve a (possibly relative) asset URL from the API against the backend base.
export function assetUrl(url) {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${BASE}${url}`
}

// Matterport Showcase URL for an embedded interactive tour.
export function showcaseSrc(modelId, { play = 1 } = {}) {
  return `https://my.matterport.com/show/?m=${modelId}&play=${play}`
}
