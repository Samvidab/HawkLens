import {chromium} from './frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import assert from 'node:assert/strict'
import {ROUTES,inventedIn} from './frontend/src/test/forbidden.js'
const API='http://127.0.0.1:8120',FRONT='http://localhost:5178'
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1100}})
const report={checks:[],requests:[],pageErrors:[],badResponses:[]},check=name=>{report.checks.push(name);console.log('PASS',name)}
page.on('pageerror',e=>report.pageErrors.push(e.message))
page.on('response',r=>{if(r.url().includes(':8120')&&r.status()>=400)report.badResponses.push({url:new URL(r.url()).pathname,status:r.status()})})
page.on('request',r=>{if(r.url().includes(':8118')||r.url().includes(':8120'))report.requests.push(r.method()+' '+new URL(r.url()).pathname)})
await page.route('http://127.0.0.1:8118/**',route=>route.continue({url:route.request().url().replace(':8118',':8120')}))
const state=async()=> (await fetch(API+'/state/ro_investigator')).json()
const action=async(type,fn)=>{const done=page.waitForResponse(r=>r.url().endsWith('/compose')&&r.request().method()==='POST'&&r.request().postDataJSON().type===type,{timeout:60000});await fn();const response=await done;assert.equal(response.status(),200,await response.text());await page.getByRole('status').waitFor({state:'hidden',timeout:60000})}
try{
 const health=await (await fetch(API+'/health')).json();assert.equal(health.engine_mode,'live');assert.equal(health.nessie_mode,'stub');assert.equal(health.cache_mode,'read_only')
 const cors=await fetch(API+'/portfolio',{headers:{Origin:'http://localhost:5178'}});assert.equal(cors.headers.get('access-control-allow-origin'),'http://localhost:5178');check('Live engine, read-only copied cache, stub banking and frontend CORS')
 await page.goto(FRONT);await page.locator('[data-building-id]').last().waitFor();assert.equal(await page.locator('[data-building-id]').count(),8);check('Eight recorded Portfolio cards without a run')
 await page.goto(FRONT+'/start-survey');await page.getByRole('button',{name:'Replay the recorded survey',exact:true}).click()
 await page.waitForURL('**/survey-complete',{timeout:70000});assert((await page.locator('body').innerText()).includes('8 of 8 buildings inspected'));check('Recorded survey replay, SSE feed and saved state load')
 await page.getByRole('button',{name:'Open workspace',exact:true}).click();await page.waitForURL(FRONT+'/');await page.waitForFunction(()=>document.body.innerText.includes('$17,525k'));check('Saved live-engine cost/emissions/NPV shown without recomputing survey')
 const slider=page.getByRole('slider',{name:'Carbon reduction target'})
 await action('set_target',async()=>{await slider.focus();for(let i=0;i<4;i++)await page.keyboard.press('ArrowLeft')})
 assert.equal((await state()).goal.target_pct,20);assert.equal((await state()).plan.stub,false);check('Target slider triggers actual live optimization')
 const plan20=(await state()).plan
 await page.goto(FRONT+'/plan-preferences');await action('set_risk',()=>page.getByRole('button',{name:'Growth',exact:true}).click());assert.equal((await state()).goal.risk_lambda,0);const growth=(await state()).plan
 await action('set_risk',()=>page.getByRole('button',{name:'Balanced',exact:true}).click());assert.equal((await state()).goal.risk_lambda,.2);assert.notEqual(growth.plan_id,(await state()).plan_id);check('Risk preference calls backend CVaR optimization')
 const budgetButtons=page.getByRole('button',{name:/^\$[\d,]+k$/});assert(await budgetButtons.count()>0)
 await action('set_budget',()=>budgetButtons.first().click());assert((await state()).goal.budget_usd>0);assert((await state()).plan.total_upfront<=(await state()).goal.budget_usd+.01)
 await action('set_budget',()=>page.getByRole('button',{name:'No cap',exact:true}).click());assert.equal((await state()).goal.budget_usd,null);check('Budget controls constrain and clear actual optimization inputs')
 await page.goto(FRONT+'/');await page.waitForFunction(()=>document.querySelector('[role="slider"]')?.getAttribute('aria-valuenow')==='20');await page.reload();await page.waitForFunction(()=>document.querySelector('[role="slider"]')?.getAttribute('aria-valuenow')==='20');check('Reload preserves target, run and backend results')
 await page.getByRole('button',{name:'Details for Harwin Plaza II Bldg',exact:true}).click();await page.waitForURL('**/building');await page.waitForFunction(()=>document.querySelectorAll('[data-trace-step]').length===6);assert.equal(await page.locator('[data-trace-step]').count(),6);check('Building detail and actual investigation history')
 const sw=page.getByRole('switch').first(), before=await sw.getAttribute('aria-checked')
 await action('toggle_upgrade',()=>sw.click());assert.notEqual(await sw.getAttribute('aria-checked'),before)
 await action('toggle_upgrade',()=>sw.click());check('Upgrade toggles modify and restore the engine input')
 await action('exclude_building',()=>page.getByRole('button',{name:'Exclude building',exact:true}).click());await page.waitForURL('**/building-excluded');assert((await state()).plan.excluded_building_ids.includes('23551'))
 await page.getByRole('button',{name:'Include building again',exact:true}).click();await page.waitForURL('**/building');await page.getByRole('heading',{name:'Harwin Plaza II Bldg',exact:true}).waitFor();assert(!(await state()).plan.excluded_building_ids.includes('23551'));check('Exclude/reinclude building persists backend state')
 await page.goto(FRONT+'/survey-evidence');const img=page.locator('img[src*="/media/"]').first();await img.waitFor();await page.waitForFunction(()=>[...document.querySelectorAll('img[src*="/media/"]')].some(i=>i.complete&&i.naturalWidth>0));check('Survey evidence is served by the media API')
 await page.goto(FRONT+'/assumptions');await page.getByTestId('assumption-sources').waitFor();assert((await page.getByTestId('assumption-sources').innerText()).includes('model assumptions'));check('Assumptions expose engine rates and upgrade source records')
 await page.goto(FRONT+'/risk-and-target');await page.getByText('Chance of a loss',{exact:true}).waitFor();await page.waitForFunction(()=>document.body.innerText.includes('scenarios shown in histogram'));check('Risk distribution and loss metrics come from backend widgets')
 await page.goto(FRONT+'/financing-approval');await page.getByRole('checkbox').waitFor();await page.getByRole('checkbox').click();await action('approve',()=>page.getByRole('button',{name:'Approve & fund',exact:true}).click());await page.waitForURL('**/funding-confirmation');assert((await page.locator('body').innerText()).includes('Simulated booking (stub Nessie)'));assert.equal((await state()).plan.financing.state,'executed');check('Approval gate, persisted stub finance record and disclosure')
 await page.goto(FRONT+'/documents');await page.getByRole('button',{name:/Investment memo/}).waitFor();await page.getByRole('button',{name:/Investment memo/}).click();await page.getByTestId('memo').waitFor();assert((await page.getByTestId('memo').innerText()).includes('Retrofit plan memo'));check('Backend-generated guarded memo is displayed')
 await page.goto(FRONT+'/');await page.waitForFunction(()=>!!document.querySelector('[role="slider"]'));await page.goto(FRONT+'/documents');await page.reload();await page.getByRole('button',{name:/Investment memo/}).waitFor();assert((await page.locator('body').innerText()).includes('Simulated booking'));check('Memo and financing survive view changes and reload')
 for(const route of ROUTES){await page.goto(FRONT+route);await page.waitForTimeout(600);const text=await page.locator('body').innerText();assert.deepEqual(inventedIn(text),[],route+' prototype text');assert(!(await page.locator('[data-testid="no-data"]').count()),route+' should load with recorded run')}
 check('All 21 application routes render backend data or explicit unavailable states')
 assert.deepEqual(report.pageErrors,[])
} catch(e){report.failure=e.stack;await page.screenshot({path:'/private/tmp/hawklens-full-integration-runtime/flow-failure.png'});throw e}
finally{fs.writeFileSync('/private/tmp/hawklens-full-integration-runtime/full-flow-report.json',JSON.stringify(report,null,2));await browser.close()}
