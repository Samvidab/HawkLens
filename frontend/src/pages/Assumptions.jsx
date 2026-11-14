import { useNavigate } from 'react-router-dom'

const ROWS = [
  ['Portfolio baseline', '2,400 tCO₂ / year', 'Sample portfolio'],
  ['Midtown electricity rate', '$0.14 / kWh', 'Example input'],
  ['Midtown grid factor', '0.35 kgCO₂ / kWh', 'Example input'],
  ['Discount rate', '7%', 'Example owner preference'],
  ['Monte Carlo scenarios', '10,000', 'Build specification'],
]

export default function Assumptions() {
  const navigate = useNavigate()
  const close = () => navigate(-1)

  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className="relative w-[1440px] h-[980px] shrink-0 bg-[rgba(34,42,49,0.35)]">
        <button
          type="button"
          aria-label="Close"
          onClick={close}
          className="absolute inset-0 w-full h-full cursor-default"
        />

        <div className="absolute left-[350px] top-[205px] w-[740px] h-[570px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[32px] top-[29px] font-semibold text-ink text-[25px]">
            Assumptions &amp; sources
          </p>
          <p className="absolute left-[32px] top-[72px] text-muted text-[13px]">
            Illustrative inputs · Validate before using real building data
          </p>
          <button
            type="button"
            onClick={close}
            className="absolute left-[657px] top-[35px] font-medium text-brand text-[14px] hover:underline"
          >
            Done
          </button>

          {ROWS.map(([label, value, note], i) => {
            const divTop = 115 + i * 64
            const rowTop = 127 + i * 64
            return (
              <div key={label}>
                <div className="absolute left-[32px] w-[676px] h-px bg-line" style={{ top: `${divTop}px` }} />
                <p className="absolute left-[32px] font-medium text-ink text-[14px]" style={{ top: `${rowTop}px` }}>
                  {label}
                </p>
                <p className="absolute left-[323px] text-ink text-[14px]" style={{ top: `${rowTop}px` }}>
                  {value}
                </p>
                <p className="absolute left-[526px] text-muted text-[11px]" style={{ top: `${rowTop + 2}px` }}>
                  {note}
                </p>
              </div>
            )
          })}

          <p className="absolute left-[32px] top-[466px] text-muted text-[13px] leading-[22px]">
            These values demonstrate the workflow, not researched underwriting.
            <br />
            The live app must attach source references to every input range.
          </p>
        </div>
      </div>
    </div>
  )
}
