import { chromium } from './frontend/node_modules/playwright/index.mjs'
const b=await chromium.launch({headless:true});const p=await b.newPage()
p.on('console',m=>{if(m.type()==='warning'||m.type()==='error')console.log('CONSOLE',m.text().replace(/[A-Za-z0-9_-]{25,}/g,'[redacted]'))})
p.on('requestfailed',r=>{const u=new URL(r.url());console.log('FAILED',u.origin+u.pathname,r.failure()?.errorText)})
await p.goto('http://localhost:5178');await p.getByRole('button',{name:'Open tour of Harwin Plaza II Bldg',exact:true}).click();await p.waitForTimeout(25000)
console.log('STATUS',await p.getByTestId('co2-tour').getAttribute('data-status'));await b.close()
