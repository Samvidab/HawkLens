// Honesty helpers: nothing shown to the user may be invented.
//   <Stub/>      a visible STUB badge next to any value that comes from a stub (sample pricing engine, stub Nessie)
//   <Estimate/>  marks a value that is an estimate (benchmark baseline, estimated footprint, assumed upgrade)
//   NA           the text shown when data is missing
//   useStub()    { engine, nessie }: true when that source is a stub
import { useRun } from '../lib/store'
import { widget } from '../lib/viewModels'

export const NA = 'not available'

export function Stub({ title = 'Placeholder value from a stub, not real pricing' }) {
  return (
    <span title={title} data-stub="true"
      className="ml-[6px] inline-block align-middle rounded-[3px] bg-[#b4532f] px-[5px] py-[1px] text-[9px] font-bold tracking-[0.6px] text-white leading-[14px]">
      STUB
    </span>
  )
}

export function Estimate({ children = 'estimate', title = 'Estimated, not measured' }) {
  return (
    <span title={title} data-estimate="true"
      className="ml-[6px] inline-block align-middle rounded-[3px] border border-[#9a8a55] px-[4px] text-[9px] font-medium tracking-[0.4px] text-[#7a693b] leading-[13px]">
      {children}
    </span>
  )
}

/** Which sources are stubs: the engine (sample pricing) and Nessie (simulated bookings). */
export function useStub() {
  const run = useRun()
  const sample = !!widget(run.layout, 'plan_table')?.sample_pricing
  return {
    engine: sample || run.health?.engine_mode === 'stub',
    nessie: run.health?.nessie_mode === 'stub',
  }
}

/** `value` if present, else "not available" (for numbers already formatted as strings). */
export const orNA = (value) => (value === null || value === undefined || value === '' || value === '—' ? NA : value)
