import Navigation from './Navigation'

// Centered 1440x980 canvas matching the Figma frame, with the shared nav.
// `active` selects the highlighted nav tab. `nav={false}` omits the bar
// (used by full-bleed "expanded"/modal screens).
// `fluid`: grow with the content (the memo and insights pages have a variable height) instead of the fixed 980 px frame.
export default function Page({ active = 'portfolio', nav = true, fluid = false, children }) {
  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className={`relative bg-white w-[1440px] shadow-sm shrink-0 ${fluid ? 'min-h-[980px]' : 'h-[980px] overflow-hidden'}`}>
        {nav && <Navigation active={active} />}
        {children}
      </div>
    </div>
  )
}
