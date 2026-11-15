import {chromium} from './frontend/node_modules/playwright/index.mjs'
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1100}})
try{
 await page.goto('http://localhost:5178')
 await page.getByRole('button',{name:'Open tour of Harwin Plaza II Bldg',exact:true}).click()
 await page.waitForFunction(()=>document.querySelector('[data-testid="co2-tour"]')?.dataset.status==='ready',{},{timeout:90000})
 const frame=page.frames().find(f=>f.url().includes('my.matterport.com'))
 console.log(JSON.stringify(await frame.evaluate(()=>[...document.querySelectorAll('[data-tag-id], [data-mattertag-id], [aria-label*="Photo taken"], [class*="tag"]')].filter(e=>(e.textContent||'').includes('Photo taken here')||[...e.attributes].some(a=>a.name.includes('tag-id'))).slice(0,12).map(e=>({tag:e.tagName,attrs:[...e.attributes].filter(a=>!a.name.includes('style')).map(a=>[a.name,a.value.slice(0,100)]),text:e.textContent.slice(0,100)})))))
 await page.screenshot({path:'/private/tmp/hawklens-portfolio-runtime/showcase-restored.png'})
}finally{await browser.close()}
