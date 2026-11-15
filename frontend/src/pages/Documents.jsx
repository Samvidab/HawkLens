import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { Sources, Stub, useStub } from '../components/Truth'
import { useOverview } from '../lib/store'
import { Markdown, downloadText } from '../lib/markdown'
import { financingModel, memoMarkdown } from '../lib/viewModels'

// Strict: lists only documents the backend actually produced for this run (the memo, the funding record).
export default function Documents() {
  const navigate = useNavigate()
  const run = useOverview()
  const { nessie } = useStub()
  const memo = memoMarkdown(run.layout)
  const fin = financingModel(run.layout, run.state)
  const docs = [
    memo && { key: 'memo', title: 'Investment memo', meta: `Markdown · plan ${fin?.planId || ''}`, open: () => navigate('/investment-memo'), highlight: true },
    fin?.executed && { key: 'funding', title: 'Reserve confirmation', meta: nessie ? 'Simulated booking (stub Nessie)' : 'Nessie sandbox record', stub: nessie, open: () => navigate('/funding-confirmation') },
  ].filter(Boolean)

  return (
    <Page active="documents">
      <div className="absolute left-[56px] top-[127px] w-[1328px] h-[105px] overflow-hidden">
        <h1 className="absolute left-0 top-0 font-semibold text-ink text-[32px]">Documents</h1>
        <p className="absolute left-0 top-[49px] text-muted text-[14px]">
          What this run has produced so far.
        </p>
      </div>

      <section className="absolute left-[56px] top-[265px] w-[768px] h-[625px] overflow-hidden">
        <p className="absolute left-[20px] top-[0px] text-muted text-[11px]">Document</p>
        <div className="absolute left-0 top-[27px] w-[768px] flex flex-col gap-[8px]">
          {!docs.length && (
            <p className="px-[20px] py-[16px] text-muted text-[14px]">
              No documents yet. The investment memo is written when you approve the plan.
            </p>
          )}
          {docs.map((d) => (
            <button
              key={d.key}
              type="button"
              onClick={d.open}
              className={`relative block w-[768px] h-[83px] rounded-[6px] text-left overflow-hidden ${d.highlight ? 'bg-[#edf3e6]' : 'hover:bg-[#f6f7f3]'}`}
            >
              <span className="absolute left-[20px] top-[16px] text-[15px] font-medium text-ink">{d.title}{d.stub && <Stub title="Simulated booking" />}</span>
              <span className="absolute left-[20px] top-[46px] text-muted text-[12px]">{d.meta}</span>
              <span className="absolute left-[724px] top-[25px] text-brand text-[20px]">›</span>
            </button>
          ))}
        </div>
      </section>

      <section className="absolute left-[880px] top-[265px] w-[504px] h-[625px] rounded-[7px] border border-line bg-white overflow-hidden">
        <div className="flex items-center justify-between h-[47px] px-[25px] bg-[#f5f7f2]">
          <p className="font-medium text-muted text-[10px] tracking-[1px]">MEMO PREVIEW</p>
        </div>
        <div className="h-[520px] overflow-y-auto px-[29px] py-[20px]">
          {memo ? <Markdown text={memo} /> : <p className="text-muted text-[13px]">The memo is not available yet.</p>}
        </div>
        {memo && (
          <button
            type="button"
            onClick={() => downloadText(`memo-${fin?.planId || 'plan'}.md`, memo)}
            className="absolute left-[29px] top-[583px] font-medium text-brand text-[13px] hover:underline"
          >
            Download memo&nbsp;&nbsp;↓
          </button>
        )}
      </section>

      <Sources banking />
    </Page>
  )
}
