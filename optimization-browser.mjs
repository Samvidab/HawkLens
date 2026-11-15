import {chromium} from './frontend/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const browser=await chromium.launch({headless:true}), page=await browser.newPage({viewport:{width:1500,height:1100}})
const errors=[];page.on('pageerror',e=>errors.push(e.message))
await page.route('http://127.0.0.1:8118/**',route=>route.continue({url:route.request().url().replace(':8118',':8120')}))
await page.addInitScript(()=>sessionStorage.setItem('hawklens.runId','ro_investigator'))
try{
 await page.goto('http://localhost:5178')
 const slider=page.getByRole('slider',{name:'Carbon reduction target'})
 await slider.waitFor()
 await page.waitForFunction(()=>document.body.innerText.includes('$17,525k'))
 await slider.focus();for(let i=0;i<4;i++)await page.keyboard.press('ArrowLeft')
 await page.waitForFunction(()=>document.querySelector('[role="slider"]')?.getAttribute('aria-valuenow')==='20')
 await page.waitForFunction(()=>!document.body.innerText.includes('updating…')&&!document.body.innerText.includes('$17,525k'),{},{timeout:30000})
 const plan=JSON.parse(fs.readFileSync('/private/tmp/hawklens-portfolio-runtime/optimization-check-data/plans/current.json'))
 assert.equal(plan.goal.target_pct,20);assert.equal(plan.stub,false);assert.equal(plan.risk_supported,true)
 assert(plan.selected.length>0);assert(plan.total_upfront!==17524612.724999994)
 assert.deepEqual(errors,[])
 console.log(JSON.stringify({browserReplan:'passed',target:plan.goal.target_pct,plan:plan.plan_id,upgrades:plan.selected.length,upfront:plan.total_upfront,engine:'live',errors}))
}finally{await browser.close()}
