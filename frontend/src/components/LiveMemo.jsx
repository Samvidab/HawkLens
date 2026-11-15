import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchMemo, generateMemo, downloadMemo } from '../lib/memoApi'

const money = n => typeof n === 'number' ? new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:0}).format(n) : 'Pending'
const number = n => typeof n === 'number' ? new Intl.NumberFormat('en-US').format(n) : 'Pending'

export default function LiveMemo({ expanded = false }) {
  const navigate = useNavigate()
  const [memo, setMemo] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { fetchMemo().then(setMemo).catch(e => setError(e.message)) }, [])
  async function generate() {
    setBusy(true); setError('')
    try { setMemo(await generateMemo(memo.plan_id)) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  async function download() {
    setBusy(true); setError('')
    try { await downloadMemo(memo.plan_id) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  return <section className={`rounded-[8px] border border-line bg-white p-7 ${expanded ? 'max-w-[850px] mx-auto mt-28' : 'w-full h-full overflow-y-auto'}`}>
    <p className="text-brand font-semibold text-sm">Hawk Lens</p>
    <h2 className="text-3xl font-semibold text-ink mt-5">Investment memo</h2>
    <p className="text-muted text-sm mt-2">Current retrofit plan · {memo?.approved ? 'Approved' : 'Draft for owner review'}</p>
    <div className="border-t border-line mt-6 pt-5">
      {error && <p role="alert" className="text-red-700 text-sm mb-4">{error}</p>}
      {!memo && !error && <p className="text-muted">Loading memo…</p>}
      {memo && <>
        <h3 className="font-semibold text-lg">Recommendation</h3>
        <p className="text-muted text-sm mt-2">Fund {memo.metrics.upgrade_count} upgrades across {memo.metrics.building_count} buildings. Expected annual cut: {number(memo.metrics.tonnes_per_year)} tonnes CO₂.</p>
        <div className="grid grid-cols-2 gap-4 mt-6 text-sm">
          <span className="text-muted">Upfront investment</span><span className="font-medium text-right">{money(memo.metrics.total_upfront)}</span>
          <span className="text-muted">Expected net present value</span><span className="font-medium text-right">{money(memo.metrics.exp_npv)}</span>
          <span className="text-muted">Worst 5% outcome (CVaR)</span><span className="font-medium text-right">{money(memo.metrics.cvar5)}</span>
          <span className="text-muted">Probability of loss</span><span className="font-medium text-right">{typeof memo.metrics.p_loss === 'number' ? `${(memo.metrics.p_loss * 100).toFixed(0)}%` : 'Pending'}</span>
        </div>
        <h3 className="font-semibold text-lg mt-7">Investment analysis</h3>
        {memo.markdown ? <div className="text-muted text-sm whitespace-pre-wrap mt-3 leading-6">{memo.markdown}</div> : <p className="text-muted text-sm mt-3">Generate a draft based on the current priced plan.</p>}
        <div className="flex gap-5 mt-8">
          <button disabled={busy} onClick={generate} className="text-brand font-medium text-sm hover:underline disabled:opacity-50">{busy ? 'Working…' : memo.markdown ? 'Regenerate memo' : 'Generate memo'}</button>
          <button disabled={busy || !memo.markdown} onClick={download} className="text-brand font-medium text-sm hover:underline disabled:opacity-50">Download PDF ↓</button>
          {!expanded && <button onClick={() => navigate('/investment-memo')} className="text-brand font-medium text-sm hover:underline">Open memo ↗</button>}
        </div>
      </>}
    </div>
  </section>
}
