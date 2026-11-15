const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options) {
  const response = await fetch(`${BASE}${path}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { message = (await response.json()).detail || message } catch {}
    throw new Error(message)
  }
  return response.json()
}

export const fetchMemo = () => request('/documents/memo')
export const generateMemo = (planId) => request('/documents/memo/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ plan_id: planId }),
})
export async function downloadMemo(planId) {
  const response = await fetch(`${BASE}/documents/memo/download?plan_id=${encodeURIComponent(planId)}`)
  if (!response.ok) {
    let message = `Download failed (${response.status})`
    try { message = (await response.json()).detail || message } catch {}
    throw new Error(message)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `hawklens-investment-memo-${planId}.pdf`
  link.click()
  URL.revokeObjectURL(url)
}
