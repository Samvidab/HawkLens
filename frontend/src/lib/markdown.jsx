// Minimal, safe markdown for the memo widget: headings, paragraphs, tables, _italic_ and **bold**.
// Builds React elements (no innerHTML), so nothing in the text can inject markup.
import React from 'react'

function inline(text, key) {
  const out = []
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const t = m[0]
    out.push(t.startsWith('**') ? <strong key={`${key}-${i++}`}>{t.slice(2, -2)}</strong> : <em key={`${key}-${i++}`}>{t.slice(1, -1)}</em>)
    last = m.index + t.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

/** Save `text` as a file in the browser (the memo is downloaded exactly as the backend wrote it). */
export function downloadText(filename, text, type = 'text/markdown') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())

export function Markdown({ text }) {
  if (!text) return null
  const blocks = String(text).replace(/\r/g, '').replace(/^(#{1,6}[^\n]+)$/gm, '\n$1\n').trim().split(/\n{2,}/)
  return (
    <div className="space-y-3 text-[13px] leading-[1.6] text-ink">
      {blocks.map((b, i) => {
        const lines = b.split('\n')
        if (/^#{1,6}\s/.test(b)) {
          const level = b.match(/^#+/)[0].length
          const body = b.replace(/^#+\s*/, '')
          return level === 1
            ? <h3 key={i} className="text-[18px] font-semibold">{inline(body, i)}</h3>
            : <h4 key={i} className="text-[15px] font-semibold">{inline(body, i)}</h4>
        }
        if (lines.length >= 2 && lines.every((l) => l.trim().startsWith('|'))) {
          const [head, , ...rows] = lines
          return (
            <table key={i} className="w-full text-[12px] border-collapse">
              <thead><tr>{cells(head).map((c, j) => <th key={j} className="text-left font-medium text-muted border-b border-line py-1 pr-3">{c}</th>)}</tr></thead>
              <tbody>{rows.map((r, k) => <tr key={k}>{cells(r).map((c, j) => <td key={j} className="border-b border-line/60 py-1 pr-3 tabular-nums">{inline(c, `${i}-${k}-${j}`)}</td>)}</tr>)}</tbody>
            </table>
          )
        }
        return <p key={i}>{inline(lines.join(' '), i)}</p>
      })}
    </div>
  )
}
