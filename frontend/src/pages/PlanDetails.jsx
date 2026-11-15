import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA, Sources, Stub, useStub } from '../components/Truth'
import { useGo } from '../lib/ui'
import { useOverview } from '../lib/store'
import { abatementGeometry, feedRows, planMetrics, planRows, planSummary, riskModel, targetModel } from '../lib/viewModels'

// Strict: metrics, chart, events and table come only from the run; nothing is drawn when the data is missing.
export default function PlanDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const run = useOverview()
  const stub = useStub().engine
  const L = run.layout
  const metrics = planMetrics(L) || []
  const rows = planRows(L) || []
  const geo = abatementGeometry(L)
  const sum = planSummary(L)
  const tm = targetModel(L)
  const risk = riskModel(L)
  const results = Object.values(run.state?.results || {})
  const nReady = results.filter((r) => r.status === 'done').length
  const activity = feedRows(run.events, 3).map((e) => ({ key: e.seq, time: `${e.time.slice(0, 5)} · ${e.agent}`, line: e.msg, meta: e.meta }))
  const cutBars = geo ? geo.bars.filter((b) => b.profitable) : []
  const costBars = geo ? geo.bars.filter((b) => !b.profitable) : []
  const rowH = rows.length > 3 ? 24 : 33
  const tableH = rows.length > 3 ? 90 + rows.length * rowH + 12 : 193
  const pickBar = async (b) => {
    if (!b.upgradeId) return
    await run.act('select_bar', { upgrade_id: b.upgradeId }).catch(() => {})
    navigate('/building')
  }

  return (
    <Page active="plan">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        What&rsquo;s in your plan
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        {sum ? sum.line : `Plan ${NA}`}
      </p>
      <button
        type="button"
        onClick={() => go('/financing-approval')}
        className="absolute left-[1206px] top-[139px] w-[178px] h-[47px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
      >
        Review &amp; approve
      </button>

      {/* Plan outcomes metric strip */}
      <div className="absolute left-[56px] top-[230px] w-[1328px] h-[94px]">
        {!metrics.length && <p className="text-muted text-[13px]">Plan metrics not available.</p>}
        {metrics.map((m, i) => (
          <div key={m.label}>
            {i > 0 && (
              <div className="absolute top-0 w-px h-[86px] bg-line" style={{ left: `${m.left - 20}px` }} />
            )}
            <p className="absolute top-0 text-muted text-[12px]" style={{ left: `${m.left}px` }}>
              {m.label}
            </p>
            <p
              className={`absolute whitespace-nowrap ${m.value === NA ? 'top-[30px] text-muted text-[16px]' : 'top-[24px] font-semibold text-ink text-[27px]'}`}
              style={{ left: `${m.left}px` }}
            >
              {m.value}{stub && m.value !== NA && <Stub />}
            </p>
            <p className="absolute top-[65px] text-muted text-[12px]" style={{ left: `${m.left}px` }}>
              {m.sub}
            </p>
          </div>
        ))}
      </div>

      {/* Abatement curve card */}
      <section className="absolute left-[56px] top-[365px] w-[880px] h-[290px] rounded-[6px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[21px] top-[18px] font-semibold text-ink text-[16px]">
          Available carbon cuts{stub && <Stub />}
        </p>
        <p className="absolute left-[21px] top-[44px] text-muted text-[12px]">
          Below zero: upgrades whose savings exceed their cost over their life.
        </p>
        {!geo && <p className="absolute left-[21px] top-[120px] text-muted text-[13px]">Abatement curve not available.</p>}
        {geo && (
          <>
            <p className="absolute left-[21px] top-[79px] text-muted text-[10px]">Lifetime net cost / tCO₂</p>
            <p className="absolute left-[475px] top-[253px] text-muted text-[10px]">Annual CO₂ avoided (t) →</p>

            {/* grid lines + axis labels (computed from the bars' own scale) */}
            <div className="absolute left-[64px] top-[212px] w-[562px] h-px bg-[#e7ebe2]" />
            <p className="absolute left-[16px] top-[207px] text-muted text-[9px]">−${geo.yLabel.toLocaleString('en-US')}</p>
            <div className="absolute left-[64px] top-[165px] w-[562px] h-px bg-[#9aa68f]" />
            <p className="absolute left-[16px] top-[160px] text-muted text-[9px]">$0</p>
            <div className="absolute left-[64px] top-[118px] w-[562px] h-px bg-[#e7ebe2]" />
            <p className="absolute left-[16px] top-[113px] text-muted text-[9px]">${geo.yLabel.toLocaleString('en-US')}</p>

            {cutBars.map((b) => (
              <div
                key={b.upgradeId}
                title={b.name}
                onClick={() => pickBar(b)}
                className="absolute bg-brand rounded-[2px] cursor-pointer hover:brightness-110"
                style={{ left: `${b.left}px`, top: '165px', width: `${b.width}px`, height: `${b.height}px` }}
              />
            ))}
            {costBars.map((b) => (
              <div
                key={b.upgradeId}
                title={b.name}
                onClick={() => pickBar(b)}
                className="absolute bg-[#dde4d5] border border-[#b9c5ae] rounded-[2px] cursor-pointer hover:brightness-95"
                style={{ left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` }}
              />
            ))}
            {tm?.tonnesNeeded != null && (
              <>
                <div className="absolute top-[110px] w-px h-[131px] bg-[#7a693b]" style={{ left: `${geo.referenceLeft(tm.tonnesNeeded)}px` }} />
                <p className="absolute top-[93px] font-medium text-[#7a693b] text-[10px]" style={{ left: `${geo.referenceLeft(tm.tonnesNeeded) - 30}px` }}>
                  Target: {tm.target}%
                </p>
              </>
            )}
            {geo.xTicks.map((t) => (
              <p key={t.label} className="absolute top-[237px] text-muted text-[9px]" style={{ left: `${t.left}px` }}>{t.label}</p>
            ))}

            <div className="absolute left-[21px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#416b4d]" />
            <p className="absolute left-[36px] top-[268px] text-muted text-[10px]">Pays for itself</p>
            <div className="absolute left-[144px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#dde4d5]" />
            <p className="absolute left-[159px] top-[268px] text-muted text-[10px]">Net cost</p>

            <div className="absolute left-[651px] top-[83px] w-px h-[182px] bg-[#e7ebe2]" />
            <p className="absolute left-[673px] top-[92px] font-medium text-muted text-[10px] tracking-[0.6px]">
              PROFITABLE CUTS
            </p>
            <p className="absolute left-[673px] top-[113px] font-semibold text-brand text-[31px]">{geo.profitableTonnes.toLocaleString('en-US')}</p>
            <p className="absolute left-[673px] top-[153px] text-muted text-[10px]">tCO₂ / year</p>
            <div className="absolute left-[673px] top-[178px] font-medium text-ink text-[12px] leading-[20px]">
              Below-zero upgrades
              <br />
              have a negative net cost.
            </div>
            <div className="absolute left-[673px] top-[240px] text-muted text-[10px] leading-[17px]">
              Bar width = carbon avoided
              <br />
              Bar height = cost per tonne
            </div>
          </>
        )}
      </section>

      {/* Survey activity card */}
      <section className="absolute left-[960px] top-[365px] w-[424px] h-[290px] rounded-[6px] border border-line bg-white overflow-hidden">
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[21px] top-[18px] font-semibold text-ink text-[16px] hover:text-brand"
        >
          Survey activity
        </button>
        {results.length > 0 && (
          <div className="absolute left-[300px] top-[19px] w-[100px] h-[23px] rounded-[5px] bg-[#edf3e6] flex items-center">
            <span className="ml-[12px] font-medium text-brand text-[10px]">{nReady} / {results.length} ready</span>
          </div>
        )}
        <p className="absolute left-[21px] top-[44px] text-muted text-[12px]">
          Latest recorded events
        </p>
        {!activity.length && <p className="absolute left-[21px] top-[82px] text-muted text-[12px]">No events loaded.</p>}
        {activity.map((a, i) => {
          const top = 82 + i * 57
          return (
            <div key={a.key ?? i}>
              <span
                className="absolute left-[21px] w-[18px] h-[18px] rounded-full bg-brand text-white text-[11px] flex items-center justify-center"
                style={{ top: `${top}px` }}
              >
                ✓
              </span>
              <p className="absolute left-[48px] font-medium text-ink text-[12px]" style={{ top: `${top}px` }}>
                {a.time}
              </p>
              <p className="absolute left-[48px] w-[360px] truncate text-muted text-[11px]" style={{ top: `${top + 18}px` }}>
                {a.line}
              </p>
              <p className="absolute left-[48px] text-muted text-[9px]" style={{ top: `${top + 33}px` }}>
                {a.meta}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[21px] top-[257px] w-[380px] h-px bg-[#e7ebe2]" />
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[21px] top-[269px] font-medium text-brand text-[11px] hover:underline"
        >
          View survey evidence
        </button>
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[388px] top-[266px] text-brand text-[15px]"
        >
          ↗
        </button>
      </section>

      {/* Upgrade breakdown table */}
      <section className="absolute left-[56px] top-[709px] w-[1328px] rounded-[6px] border border-line bg-white overflow-hidden" style={{ height: tableH }}>
        <p className="absolute left-[21px] top-[16px] font-semibold text-ink text-[16px]">
          Upgrade breakdown
        </p>
        <p className="absolute left-[237px] top-[21px] text-muted text-[11px]">
          {sum ? sum.count : `Upgrades ${NA}`}
        </p>
        <p className="absolute left-[919px] top-[20px] text-muted text-[11px]">
          Worst 5% average: {risk ? `${risk.worst5} NPV` : NA}{stub && risk && <Stub />}
        </p>
        <button
          type="button"
          onClick={() => go('/investment-memo')}
          className="absolute left-[1149px] top-[11px] w-[156px] h-[31px] rounded-[5px] bg-[#f1f4ed] text-left"
        >
          <span className="ml-[12px] font-medium text-brand text-[11px]">Investment memo&nbsp;&nbsp;↗</span>
        </button>

        <div className="absolute left-0 top-[54px] w-[1326px] h-[29px] bg-[#f6f7f3]" />
        {['UPGRADE BUNDLE', 'COVERAGE', 'UPFRONT COST', 'ANNUAL CO₂ CUT', 'EXPECTED NPV'].map((h, i) => (
          <p
            key={h}
            className="absolute top-[63px] font-medium text-muted text-[9px] tracking-[0.6px]"
            style={{ left: `${[21, 417, 655, 895, 1135][i]}px` }}
          >
            {h}
          </p>
        ))}
        {!rows.length && <p className="absolute left-[21px] top-[92px] text-muted text-[12px]">No upgrades in the plan.</p>}
        {rows.map((r, i) => {
          const top = 90 + i * rowH
          return (
            <div key={r.name}>
              {i > 0 && (
                <div className="absolute left-[21px] w-[1284px] h-px bg-[#e7ebe2]" style={{ top: `${top - 7}px` }} />
              )}
              <button
                type="button"
                onClick={() => navigate('/building')}
                className="absolute left-[21px] font-medium text-ink text-[12px] hover:text-brand"
                style={{ top: `${top}px` }}
              >
                {r.name}
              </button>
              <p className="absolute left-[417px] text-muted text-[12px]" style={{ top: `${top}px` }}>
                {r.coverage}{r.unverified ? ` · ${r.unverified} unverified` : ''}
              </p>
              <p className="absolute left-[655px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                {r.cost}{stub && r.cost !== NA && <Stub />}
              </p>
              <p className="absolute left-[895px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                {r.co2}
              </p>
              <p className="absolute left-[1135px] font-medium text-brand text-[12px]" style={{ top: `${top}px` }}>
                {r.npv}
              </p>
            </div>
          )
        })}
      </section>

      <Sources />
      <button
        type="button"
        onClick={() => go('/risk-and-target')}
        className="absolute left-[1174px] top-[947px] font-medium text-brand text-[13px] hover:underline"
      >
        Risk &amp; target details&nbsp;&nbsp;→
      </button>
    </Page>
  )
}
