import {useEffect, useRef, useState} from 'react'

// Image and recorded marks share one measured frame. No object-cover crop or stretched coordinates.
export default function RecordedImage({image}) {
  const root = useRef(null)
  const [space, setSpace] = useState({width:0,height:0})
  const [native, setNative] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const measure = () => { const r=root.current?.getBoundingClientRect(); if(r)setSpace({width:r.width,height:r.height}) }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    if(root.current)observer?.observe(root.current)
    return ()=>observer?.disconnect()
  }, [])
  useEffect(()=>{setNative(null);setFailed(false)},[image.url])
  const scale = native ? Math.min(space.width/native.width,space.height/native.height,1) : 0
  return <div ref={root} className="absolute inset-0 flex items-center justify-center">
    {failed ? <p className="text-muted p-4">Recorded survey image unavailable.</p> : <div className="relative" style={native?{width:native.width*scale,height:native.height*scale}:undefined}>
      <img src={image.url} alt={image.title} onLoad={e=>setNative({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})}
        onError={()=>setFailed(true)} style={{display:'block',width:'100%',height:'100%'}} />
      {native && <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Recorded survey marks" className="absolute inset-0 w-full h-full pointer-events-none">
        {(image.marks||[]).filter(m=>m.image_id===image.id).map((m,i)=>{
          const b=m.bbox,valid=Array.isArray(b)&&b.length===4&&b.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>=0&&x<=1)&&b[2]>b[0]&&b[3]>b[1]
          if(!valid)return null
          return <g key={i} fill="none"><title>{m.label||'Recorded mark'}</title>{[['#111',6],['#ffdd00',3]].map(([stroke,width])=><ellipse key={stroke} cx={(b[0]+b[2])/2} cy={(b[1]+b[3])/2} rx={(b[2]-b[0])/2} ry={(b[3]-b[1])/2} stroke={stroke} strokeWidth={width} vectorEffect="non-scaling-stroke" />)}</g>
        })}
      </svg>}
    </div>}
  </div>
}
