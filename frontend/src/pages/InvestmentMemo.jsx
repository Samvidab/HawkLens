import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { Sources } from '../components/Truth'
import { useOverview } from '../lib/store'
import { Markdown, downloadText } from '../lib/markdown'
import { financingModel, memoMarkdown } from '../lib/viewModels'

// Strict: the memo exactly as the backend wrote it (every number in it comes from the plan); nothing else.
export default function InvestmentMemo() {
  const navigate = useNavigate()
  const run = useOverview()
  const memo = memoMarkdown(run.layout)
  const fin = financingModel(run.layout, run.state)

  return (
    <Page nav={false} fluid>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1207px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back&nbsp;&nbsp;×
      </button>

      <section className="relative mx-auto mt-[120px] mb-[80px] w-[760px] rounded-[8px] border border-line bg-white overflow-hidden" data-testid="memo">
        <div className="flex items-center justify-between h-[57px] px-[30px] bg-[#f5f7f2]">
          <p className="font-medium text-muted text-[12px] tracking-[1.2px]">INVESTMENT MEMO</p>
          <p className="text-muted text-[12px]">{fin?.planId ? `Plan ${fin.planId}` : ''}{fin?.executed ? ' · approved' : ''}</p>
        </div>
        <div className="px-[36px] py-[28px]">
          {memo ? <Markdown text={memo} /> : (
            <p className="text-muted text-[14px]">The memo is not available yet. It is written from the plan when you approve it.</p>
          )}
        </div>
        {memo && (
          <div className="px-[36px] pb-[28px]">
            <button
              type="button"
              onClick={() => downloadText(`memo-${fin?.planId || 'plan'}.md`, memo)}
              className="font-medium text-brand text-[15px] hover:underline"
            >
              Download memo (Markdown)&nbsp;&nbsp;↓
            </button>
          </div>
        )}
      </section>
      <Sources banking className="absolute left-[56px] bottom-[24px]" />
    </Page>
  )
}
