import {chromium} from './frontend/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1100}})
const report=[]
try{
 await page.route('http://127.0.0.1:8118/**',route=>route.continue({url:route.request().url().replace(':8118',':8120')}))
 await page.addInitScript(()=>sessionStorage.setItem('hawklens.runId','ro_investigator'))
 await page.goto('http://localhost:5178/plan-preferences')
 await page.getByRole('button',{name:'Cautious',exact:true}).waitFor()
 const state=await (await fetch('http://127.0.0.1:8120/state/ro_investigator')).json()
 const target=state.goal.risk_lambda===.4?'Growth':'Cautious'
 let injected=false
 await page.route('**/compose',route=>{
  if(!injected&&route.request().method()==='POST'&&route.request().postDataJSON().type==='set_risk'){
   injected=true;return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Intentional integration-test outage'})})
  }
  return route.continue({url:route.request().url().replace(':8118',':8120')})
 })
 await page.getByRole('button',{name:target,exact:true}).click()
 await page.getByRole('alert').waitFor()
 assert((await page.getByRole('alert').innerText()).includes('Intentional integration-test outage'))
 assert.equal((await (await fetch('http://127.0.0.1:8120/state/ro_investigator')).json()).goal.risk_lambda,state.goal.risk_lambda)
 await page.getByRole('button',{name:'Retry loading saved state',exact:true}).click();await page.getByRole('alert').waitFor({state:'hidden'})
 report.push('Failed optimization shows API error, retains backend goal, and allows state retry; no data fallback')
 const unavailable=await browser.newPage()
 await unavailable.route('http://127.0.0.1:8118/**',r=>r.abort())
 await unavailable.goto('http://localhost:5178/')
 await unavailable.getByTestId('no-data').waitFor();assert.equal(await unavailable.locator('[data-building-id]').count(),0)
 await unavailable.getByRole('alert').waitFor();report.push('Unavailable backend displays error/unavailable state, never sample buildings')
 await unavailable.close()
 console.log(JSON.stringify(report))
}finally{fs.writeFileSync('/private/tmp/hawklens-full-integration-runtime/failure-path-report.json',JSON.stringify(report));await browser.close()}
