// Which of THEIR buildings (the grid on their Portfolio page) get verified CO2 highlighting, and how many tags each.
// Same rule as the site: a building matches when its Matterport model id is the scan our agents surveyed and that scan has
// verified items. No dependencies (node 18+):
//   node co2-demo/check_matches.mjs [THEIR_API=http://localhost:8010] [OUR_API=http://localhost:8000]
const [THEIRS = 'http://localhost:8010', OURS = 'http://localhost:8000'] = process.argv.slice(2)
const get = async (base, path) => { const r = await fetch(base + path); if (!r.ok) throw new Error(`${base}${path} ${r.status}`); return r.json() }

const their = (await get(THEIRS, '/properties?limit=24')).results // their page shows the first 24
const ours = await get(OURS, '/portfolio')
const rows = []
const surveyed = new Map() // model id -> { building, data }
const linked = new Map() // any linked model id -> building name
for (const b of ours.buildings) {
  const data = await get(OURS, `/co2_equipment/${encodeURIComponent(b.building_id)}`)
  if (data.model_id && data.items.length) surveyed.set(data.model_id, { name: b.name, data })
  for (const id of [b.matterport_model_id, ...(b.matterport_model_ids || [])].filter(Boolean)) linked.set(id, b.name)
}
for (const p of their) {
  const hit = surveyed.get(p.id)
  const other = !hit && linked.get(p.id)
  rows.push({
    their_building: `${p.name} (${p.id})`,
    result: hit ? `MATCH: ${hit.name}` : other ? `same building as ${other}, but not the surveyed scan: nothing` : 'not in our 8: nothing',
    tags: hit ? hit.data.items.length : 0,
  })
}
console.table(rows)
console.log(`their buildings shown: ${their.length} | matched: ${rows.filter((r) => r.tags).length} | tags: ${rows.reduce((n, r) => n + r.tags, 0)}`)
const missing = [...surveyed].filter(([id]) => !their.some((p) => p.id === id)).map(([id, v]) => `${v.name} (${id})`)
if (missing.length) console.log(`our surveyed scans NOT in their grid: ${missing.join(', ')}`)
