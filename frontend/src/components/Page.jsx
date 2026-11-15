
import Navigation from './Navigation'
import TopoBackground from './TopoBackground'

export default function Page({
  active = 'portfolio',
  nav = true,
  children
}) {
  return (
    <div className="relative min-h-full w-full flex justify-center py-10 px-4">
      <TopoBackground />

      <div className="relative z-10 bg-white w-[1440px] h-[980px] shadow-sm shrink-0 overflow-hidden">
        {nav && <Navigation active={active} />}
        {children}
      </div>
    </div>
  )
}
