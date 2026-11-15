import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRun } from '../lib/store'
import { Markdown, downloadText } from '../lib/markdown'
import { memoMarkdown } from '../lib/viewModels'
import { fetchMemo, generateMemo, downloadMemo } from '../lib/memoApi'

const money = n => typeof n === 'number' ? new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:0}).format(n) : 'Pending'
const number = n => typeof n === 'number' ? new Intl.NumberFormat('en-US').format(n) : 'Pending'

export default function LiveMemo({ expanded = false }) {
  const navigate = useNavigate()
  const run = useRun()
  const recordedMemo = memoMarkdown(run.layout, run.state)
  const [memo, setMemo] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { let live=true; setMemo(null); setError(''); fetchMemo().then(m => { if(live) { if(run.state?.plan_id && m.plan_id !== run.state.plan_id) setError('The backend current plan differs from this survey. Open your current plan before generating a memo.'); else setMemo(m) } }).catch(e => live && setError(e.message)); return () => { live=false } }, [run.state?.plan_id])
  async function generate() {
    setBusy(true); setError('')
    try { setMemo(await generateMemo(memo.plan_id, run.runId)); await run.refresh() }
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
    <p className="text-muted text-xs mt-2">Modeled estimates · generating a draft does not approve financing.</p>
    <h2 className="text-3xl font-semibold text-ink mt-5">Investment memo</h2>
    <p className="text-muted text-sm mt-2">Current retrofit plan · {memo?.approved ? 'Approved' : 'Draft for owner review'}</p>
    <div className="border-t border-line mt-6 pt-5">
      {error && <p role="alert" className="text-red-700 text-sm mb-4">{error}</p>}
      {!memo && recordedMemo && <><Markdown text={recordedMemo} /><button className="text-brand underline" onClick={() => downloadText(`memo-${run.state?.plan_id || 'recorded'}.md`, recordedMemo)}>Download saved memo (Markdown)</button></>}
      {!memo && !recordedMemo && !error && <p className="text-muted">Loading memo…</p>}
      {memo && <>
        <div className="flex flex-wrap gap-4 mb-6">
          <button disabled={busy} onClick={generate} className="text-brand font-medium text-sm hover:underline disabled:opacity-50">{busy ? 'Working…' : memo.markdown ? 'Regenerate memo' : 'Generate memo'}</button>
          <button disabled={busy || !memo.markdown} onClick={download} className="text-brand font-medium text-sm hover:underline disabled:opacity-50">Download PDF ↓</button>
          <button onClick={() => downloadText(`memo-${memo.plan_id}.md`, memo.markdown)} disabled={!memo.markdown} className="text-brand font-medium text-sm hover:underline disabled:opacity-50">Download Markdown ↓</button>
          {!expanded && <button onClick={() => navigate('/investment-memo')} className="text-brand font-medium text-sm hover:underline">Open memo ↗</button>}
        </div>
        <h3 className="font-semibold text-lg">Modeled plan summary</h3>
        <p className="text-muted text-sm mt-2">Plan includes {memo.metrics.upgrade_count} upgrades across {memo.metrics.building_count} buildings. Modeled annual cut: {number(memo.metrics.tonnes_per_year)} tonnes CO₂.</p>
        <div className="grid grid-cols-2 gap-4 mt-6 text-sm">
          <span className="text-muted">Upfront investment</span><span className="font-medium text-right">{money(memo.metrics.total_upfront)}</span>
          <span className="text-muted">Expected net present value</span><span className="font-medium text-right">{money(memo.metrics.exp_npv)}</span>
          <span className="text-muted">Worst 5% outcome (CVaR)</span><span className="font-medium text-right">{money(memo.metrics.cvar5)}</span>
          <span className="text-muted">Probability of loss</span><span className="font-medium text-right">{typeof memo.metrics.p_loss === 'number' ? `${(memo.metrics.p_loss * 100).toFixed(0)}%` : 'Pending'}</span>
        </div>
        <h3 className="font-semibold text-lg mt-7">Investment analysis</h3>
        {memo.markdown ? <div className="mt-3" data-testid="live-memo-markdown"><Markdown text={memo.markdown} /></div> : <p className="text-muted text-sm mt-3">Generate a draft based on the current priced plan.</p>}

      </>}
    </div>
  </section>
}
