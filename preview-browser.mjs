import { chromium } from './frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import assert from 'node:assert/strict'
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
const errors=[], posts=[]
page.on('pageerror',e=>errors.push(e.message))
page.on('request',r=>{if(r.method()==='POST' && r.url().startsWith(base)) posts.push(r.url())})
const report={api:base,frontend:'http://localhost:5178',buildings:[],errors,posts}
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
 for (const b of portfolio.buildings){
  const data=await (await fetch(base+'/co2_equipment/'+b.building_id)).json()
  await page.getByRole('button',{name:`Open tour of ${b.name}`,exact:true}).click()
  const box=page.getByTestId('co2-tour')
  await box.waitFor()
  await page.waitForFunction(()=>['ready','failed','no-key','no-tour','no-data'].includes(document.querySelector('[data-testid="co2-tour"]')?.dataset.status),{},{timeout:90000})
  const status=await box.getAttribute('data-status');let visited=0
  const tags=Number(await box.getAttribute('data-tags'))
  if(status==='ready'){
   assert.equal(tags,data.items.length)
   for(let i=0;i<data.items.length;i++){
    const button=page.getByTestId(`co2-item-${i}`)
    assert((await button.innerText()).includes('Photo taken here'))
    await button.click()
    await page.waitForFunction(i=>{const b=document.querySelector('[data-testid="co2-tour"]');return b?.dataset.focusIndex===String(i)&&['open','failed'].includes(b.dataset.focusState)},i,{timeout:30000})
    assert.equal(await box.getAttribute('data-focus-state'),'open')
    assert.equal(await box.getAttribute('data-current-sweep'),await box.getAttribute('data-focus-sweep'))
    assert.equal(await box.getAttribute('data-docked-tag'),await box.getAttribute('data-focus-tag'))
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
 fs.writeFileSync('/private/tmp/hawklens-portfolio-runtime/browser-report.json',JSON.stringify(report,null,2))
 await browser.close()
}
