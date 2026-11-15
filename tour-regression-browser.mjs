import { chromium } from './frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import assert from 'node:assert/strict'
import {createHash} from 'node:crypto'
const base = 'http://127.0.0.1:8118'
const portfolio = await (await fetch(base + '/portfolio')).json()
const source = JSON.parse(fs.readFileSync('/private/tmp/hawklens-portfolio-runtime/data/portfolio.json'))
assert.deepEqual(portfolio.buildings.map(b => b.building_id), source.buildings.map(b => b.building_id))
for (const b of portfolio.buildings) {
 const original = source.buildings.find(x => x.building_id === b.building_id)
 const dir = '/private/tmp/hawklens-portfolio-runtime/data/buildings/' + b.building_id
 const profile = JSON.parse(fs.readFileSync(dir + '/profile.json'))
 const tour = JSON.parse(fs.readFileSync(dir + '/tour.json'))
 for (const [field,key] of Object.entries({name:'name',address:'address',lat:'lat',lon:'lon',stories:'stories',year_built:'year_built'})) assert.equal(b[field], original[field] ?? profile[key] ?? null)
 assert.equal(b.sqft, original.rba_sqft ?? profile.rba_sqft ?? null)
 assert.equal(b.matterport_model_id, tour.model_id)
 assert.equal(b.showcase_url, tour.available ? tour.showcase_url : null)
}
const browser = await chromium.launch({headless:true})
const page = await browser.newPage({ viewport:{width:1500,height:1100} })
const errors=[], posts=[], consoleErrors=[]
page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text().replace(/[A-Za-z0-9_-]{25,}/g,'[redacted]'))})
fs.mkdirSync('/private/tmp/hawklens-portfolio-runtime/evidence-shots',{recursive:true})
page.on('pageerror',e=>errors.push(e.message))
page.on('request',r=>{if(r.method()==='POST' && r.url().startsWith(base)) posts.push(r.url())})
const report={api:base,frontend:'http://localhost:5178',buildings:[],evidence:[],errors,consoleErrors,posts}
try {
 await page.goto(report.frontend)
 await page.locator('[data-building-id]').last().waitFor()
 assert.equal(await page.locator('[data-building-id]').count(),8)
 for(const b of portfolio.buildings){
  const card=page.locator(`[data-building-id="${b.building_id}"]`)
  assert.equal(await card.isVisible(),true)
  const box=await card.boundingBox();assert(box.y+box.height<1100,'card within viewport')
  assert((await card.innerText()).includes(b.name))
 }
 await page.screenshot({path:'/private/tmp/hawklens-portfolio-runtime/portfolio.png',fullPage:true})
 for (const b of portfolio.buildings.filter(b=>!process.env.ONLY_BUILDING || b.building_id===process.env.ONLY_BUILDING)){
  const data=await (await fetch(base+'/co2_equipment/'+b.building_id)).json()
  await page.getByRole('button',{name:`Open tour of ${b.name}`,exact:true}).click()
  const box=page.getByTestId('co2-tour')
  await box.waitFor()
  await page.waitForFunction(()=>['ready','failed','no-key','no-tour','no-data'].includes(document.querySelector('[data-testid="co2-tour"]')?.dataset.status),{},{timeout:90000})
  const status=await box.getAttribute('data-status');let visited=0
  const tags=Number(await box.getAttribute('data-tags'))
  if(status==='ready'){
    const frame=page.locator('[data-testid="co2-tour-frame"] iframe')
    await page.waitForFunction(()=>document.querySelector('[data-testid="co2-tour"]')?.dataset.cameraZoom!=='')
    const z=Number(await box.getAttribute('data-camera-zoom'))
    const bounds=await frame.boundingBox()
    await page.mouse.move(bounds.x+bounds.width*0.45,bounds.y+bounds.height*0.5)
    // SDK ready can precede the Showcase introductory overlay; retry a real wheel
    // gesture after it settles rather than claiming an ignored gesture zoomed.
    let zoomed=false
    for(let attempt=0;attempt<3 && !zoomed;attempt++){
      await page.mouse.wheel(0,-400)
      try { await page.waitForFunction(z=>Number(document.querySelector('[data-testid="co2-tour"]').dataset.cameraZoom)!==z,z,{timeout:10000}); zoomed=true } catch {}
    }
    if(!zoomed){await page.screenshot({path:'/private/tmp/hawklens-portfolio-runtime/native-zoom-failure.png'});console.log('ZOOM STATE',await box.evaluate(el=>({...el.dataset})));}
    assert(zoomed,b.name+' native zoom')
    const rotation=await box.getAttribute('data-camera-rotation')
    await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*0.45+90,bounds.y+bounds.height*0.5+40,{steps:8});await page.mouse.up()
    await page.waitForFunction(r=>document.querySelector('[data-testid="co2-tour"]').dataset.cameraRotation!==r,rotation,{timeout:10000})
  }
  assert.equal(status,'ready',b.name+' tour must load')
  if(status==='ready'){
   assert.equal(tags,data.items.length)
   for(let i=0;i<data.items.length;i++){
    const button=page.getByTestId(`co2-item-${i}`)
    assert((await button.innerText()).includes('Photo taken here'))
    await button.click()
    try {
      await page.waitForFunction(i=>{const b=document.querySelector('[data-testid="co2-tour"]');return b?.dataset.focusIndex===String(i)&&['open','failed'].includes(b.dataset.focusState)},i,{timeout:45000})
    } catch(e) {
      console.log('FAILED ITEM',b.building_id,i,await box.evaluate(el=>({...el.dataset})))
      await page.screenshot({path:'/private/tmp/hawklens-portfolio-runtime/tour-regression-failure.png'})
      throw e
    }
    assert.equal(await box.getAttribute('data-focus-state'),'open')
    assert.equal(await box.getAttribute('data-current-sweep'),await box.getAttribute('data-focus-sweep'))
    assert.equal(await box.getAttribute('data-docked-tag'),await box.getAttribute('data-focus-tag'))
    assert.equal(await page.getByTestId('evidence-image').count(),0,'tag selection must leave Showcase interactive')
    const tourFrame=page.locator('[data-testid="co2-tour-frame"] iframe')
    await tourFrame.evaluate(el=>el.dataset.regressionIdentity='preserved')
    const savedCamera={rotation:await box.getAttribute('data-camera-rotation'),zoom:await box.getAttribute('data-camera-zoom'),sweep:await box.getAttribute('data-current-sweep')}
    await page.getByRole('button',{name:'Inspection Close-Up',exact:true}).click()
    const item=data.items[i]
    const image=page.getByTestId('evidence-image')
    await image.waitFor()
    await page.waitForFunction(()=>{const img=document.querySelector('[data-testid="evidence-image"]');return img?.complete && img.naturalWidth>0})
    assert.equal(await image.getAttribute('src'),base+item.image_url)
    const marks=item.image_marks.filter(m=>m.image_id===item.image_id && m.bbox)
    assert.equal(await page.getByTestId('evidence-mark').count(),marks.length)
    const check=async(native=false)=>{
      // Capture geometry atomically: zoom recenters the viewport on the next frame.
      // Separate Playwright evaluations could otherwise compare different scroll frames.
      const snapshot=await page.evaluate(()=>{
        const image=document.querySelector('[data-testid="evidence-image"]')
        const overlay=document.querySelector('[data-testid="evidence-overlay"]')
        return {w:image.naturalWidth,h:image.naturalHeight,filter:getComputedStyle(image).filter,
          rect:image.getBoundingClientRect().toJSON(),overlay:overlay.getBoundingClientRect().toJSON(),
          ellipses:[...document.querySelectorAll('[data-testid="evidence-mark"]')].map(group=>{
            const el=group.querySelector('ellipse'),b=el.getBBox(),m=el.getScreenCTM()
            const a=new DOMPoint(b.x,b.y).matrixTransform(m),z=new DOMPoint(b.x+b.width,b.y+b.height).matrixTransform(m)
            return {x:a.x,y:a.y,width:z.x-a.x,height:z.y-a.y}
          })}
      })
      assert.equal(snapshot.w,2048);assert.equal(snapshot.h,2048);assert.equal(snapshot.filter,'none')
      const rect=snapshot.rect
      if(native){assert.equal(rect.width,2048);assert.equal(rect.height,2048)}
      for(const key of ['x','y','width','height'])assert(Math.abs(snapshot.overlay[key]-rect[key])<1,'overlay/image bounds '+key)
      for(const [j,mark] of marks.entries()){
        const expected={x:rect.x+mark.bbox[0]*rect.width,y:rect.y+mark.bbox[1]*rect.height,width:(mark.bbox[2]-mark.bbox[0])*rect.width,height:(mark.bbox[3]-mark.bbox[1])*rect.height}
        for(const key of Object.keys(expected))assert(Math.abs(snapshot.ellipses[j][key]-expected[key])<1,'ellipse derived from recorded bbox '+key)
      }
    }
    await check()
    await page.screenshot({path:`/private/tmp/hawklens-portfolio-runtime/evidence-shots/${b.building_id}-${i}-fit.png`})
    await page.getByRole('button',{name:'View at original size (1:1)',exact:true}).click()
    await check(true)
    await page.getByTestId('evidence-image-scroll').evaluate((el,bbox)=>{el.scrollLeft=Math.max(0,(bbox[0]+bbox[2])*1024-el.clientWidth/2);el.scrollTop=Math.max(0,(bbox[1]+bbox[3])*1024-el.clientHeight/2)},marks[0].bbox)
    await check(true)
    await page.getByRole('button',{name:'Zoom in',exact:true}).click()
    await page.waitForFunction(()=>document.querySelector('[data-testid="evidence-image"]')?.getBoundingClientRect().width===2560)
    await check()
    const scroll=page.getByTestId('evidence-image-scroll')
    await scroll.evaluate(el=>{el.scrollLeft=200;el.scrollTop=200})
    const bounds=await scroll.boundingBox()
    await page.mouse.move(bounds.x+250,bounds.y+250);await page.mouse.down();await page.mouse.move(bounds.x+170,bounds.y+180,{steps:5});await page.mouse.up()
    assert((await scroll.evaluate(el=>el.scrollLeft))>250,'drag pans image')
    await check()
    const beforeWheel=await image.evaluate(el=>el.getBoundingClientRect().width)
    await page.mouse.move(bounds.x+300,bounds.y+300);await page.mouse.wheel(0,-100)
    await page.waitForFunction(w=>document.querySelector('[data-testid="evidence-image"]')?.getBoundingClientRect().width>w,beforeWheel)
    await check()
    await page.getByRole('button',{name:'1:1 pixels',exact:true}).click();await check(true)
    await page.screenshot({path:`/private/tmp/hawklens-portfolio-runtime/evidence-shots/${b.building_id}-${i}-native.png`})
    await page.getByRole('button',{name:'Fit image',exact:true}).click()
    await page.setViewportSize({width:1000,height:800});await check();await page.setViewportSize({width:1500,height:1100})
    const images=JSON.parse(fs.readFileSync('/private/tmp/hawklens-portfolio-runtime/data/buildings/'+b.building_id+'/images.json'))
    const response=await fetch(base+item.image_url),body=Buffer.from(await response.arrayBuffer())
    assert.equal(response.status,200)
    assert.equal(createHash('sha256').update(body).digest('hex'),createHash('sha256').update(fs.readFileSync(images[item.image_id].local_path)).digest('hex'))
    report.evidence.push({building:b.building_id,index:i,image:item.image_id,marks:marks.length,originalPixels:[2048,2048],byteIdentical:true,alignedAtFitNativeResize:true})
    // Escape closes evidence only, preserving its parent tour and navigation.
    await page.getByTestId('return-to-tour').click()
    assert.equal(await page.getByTestId('evidence-image').count(),0)
    assert.equal(await page.getByTestId('co2-tour').count(),1)
    assert.equal(await tourFrame.getAttribute('data-regression-identity'),'preserved','Showcase iframe was not replaced')
    assert.equal(await box.getAttribute('data-camera-rotation'),savedCamera.rotation)
    assert.equal(await box.getAttribute('data-camera-zoom'),savedCamera.zoom)
    assert.equal(await box.getAttribute('data-current-sweep'),savedCamera.sweep)
    visited++
   }
  }
  report.buildings.push({id:b.building_id,name:b.name,tour:b.matterport_model_id,status,eligible:data.items.length,tags,visited})
  console.log(JSON.stringify(report.buildings.at(-1)))
  await page.getByRole('button',{name:'Close tour',exact:true}).click()
 }
 await page.evaluate(()=>sessionStorage.setItem('hawklens.runId','ro_investigator'))
 await page.reload()
 await page.waitForFunction(()=>document.body.innerText.includes('$17,525k'),{},{timeout:20000}).catch(()=>{})
 const state=await (await fetch(base+'/state/ro_investigator')).json()
 assert.equal(state.plan_id,'91235cb8b3dd')
 report.recordedPlan=state.plan_id
 report.recordedMetricsText=await page.locator('body').innerText()
 assert(report.recordedMetricsText.includes('$17,525k'))
 assert(report.recordedMetricsText.includes('3,859 tonnes / year'))
 assert(report.recordedMetricsText.includes('−$3,291k'))
 report.sourcesVerified = true
 await page.screenshot({path:'/private/tmp/hawklens-portfolio-runtime/portfolio-with-plan.png',fullPage:true})
 assert.equal(posts.length,0,'browser checks must not regenerate or recompose saved results')
 assert.deepEqual(errors,[])
} finally {
 fs.writeFileSync('/private/tmp/hawklens-portfolio-runtime/tour-regression-browser-report.json',JSON.stringify(report,null,2))
 await browser.close()
}
