import Navigation from './Navigation'

// Centered 1440x980 canvas matching the Figma frame, with the shared nav.
// `active` selects the highlighted nav tab. `nav={false}` omits the bar
// (used by full-bleed "expanded"/modal screens).
export default function Page({ active = 'portfolio', nav = true, children }) {
  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className="relative bg-white w-[1440px] h-[980px] shadow-sm shrink-0 overflow-hidden">
        {nav && <Navigation active={active} />}
        {children}
      </div>
    </div>
  )
}
