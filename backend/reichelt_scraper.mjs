// Regular Chromium browsing, no login, CAPTCHA solving or anti-detection plugins.
import {chromium} from '../frontend/node_modules/playwright/index.mjs';
import {pathToFileURL} from 'node:url';

const normalize=value=>String(value||'').trim().replace(/\s+/g,' ').toUpperCase();
export function allowedProductURL(value) {
 try {
  const url=new URL(value);
  return url.protocol==='https:'&&['www.reichelt.de','www.reichelt.com'].includes(url.hostname)&&!url.username&&!url.password&&!url.port&&url.pathname.includes('/shop/produkt/');
 } catch {return false;}
}

export async function extractProduct(page, article, allowMPN=false) {
 const data=await page.evaluate(()=>{
  const text=selector=>document.querySelector(selector)?.textContent.trim()||'';
  const productDetails=[];
  for(const list of document.querySelectorAll('.articleTechnicalData .articleAttribute')) {
   const cells=[...list.children].filter(el=>el.tagName==='LI');
   for(let i=0;i+1<cells.length;i+=2)productDetails.push({name:cells[i].textContent.trim(),value:cells[i+1].textContent.trim()});
  }
  const sheets=[...document.querySelectorAll('.articleDatasheet a[href],.tab3 a[href]')].filter(a=>/datenblatt|datasheet/i.test(a.textContent));
  return {articleNumber:text('.productBuy [itemprop="sku"]')||text('h1 ~ small [itemprop="sku"]'),
   productTitle:text('h1[itemprop="name"]')||text('h1'),manufacturer:text('.articleAttribute [itemprop="brand"]'),
   mpn:text('.articleAttribute [itemprop="mpn"]'),productDescription:text('[itemprop="description"]'),
   categories:[...document.querySelectorAll('[itemtype="http://schema.org/ListItem"] [itemprop="name"]')].map(e=>e.textContent.trim()),
   categoryNodes:[...document.querySelectorAll('#breadcrumb a[itemprop="item"]')].map(link=>({id:Number(link.href.match(/\/shop\/kategorie\/[^/?]+-(\d+)(?:\?|$)/)?.[1])||null,name:link.textContent.trim()})).filter(node=>node.id),
   productDetails,url:location.href,datasheet_url:sheets[0]?.href||''};
 });
 if(!data.articleNumber||(normalize(data.articleNumber)!==normalize(article)&&!(allowMPN&&normalize(data.mpn)===normalize(article))))throw new Error('Artikelnummer oder Herstellerteilenummer auf der Produktseite stimmt nicht exakt überein.');
 if(!data.productTitle||!data.productDetails.length)throw new Error('Keine technischen Produktdaten gefunden. Reichelt-Seite bitte manuell prüfen.');
 return data;
}

export async function searchProduct(page, article, allowMPN=false) {
 const result=await page.evaluate(expected=>{
  const normalize=value=>String(value||'').trim().replace(/\s+/g,' ').toUpperCase();
  const urls=[],exact=[];
  for(const link of document.querySelectorAll('a[href*="/shop/produkt/"]')) {
   const match=link.innerText.match(/Artikel-Nr\.:\s*([^\n]+)/i);
   if(match){urls.push(link.href);if(normalize(match[1])===normalize(expected))exact.push(link.href);}
  }
  return {all:[...new Set(urls)],exact:[...new Set(exact)]};
 },article);
 let matches=result.exact;
 // An MPN is not shown in search cards. Only inspect an unambiguous result,
 // then verify its complete MPN on the product page before returning any data.
 if(!matches.length&&allowMPN){
  const total=(await page.title()).match(/hatte\s+([\d.]+)\s+Treffer/i);
  if(!total||Number(total[1].replaceAll('.',''))!==1||result.all.length!==1)throw new Error('Kein eindeutiger Treffer. Bei mehreren Treffern bitte die Reichelt-Artikelnummer verwenden.');
  matches=result.all;
 }
 if(matches.length!==1||!allowedProductURL(matches[0]))throw new Error('Kein eindeutiger Treffer mit exakt dieser Reichelt-Artikelnummer.');
 return matches[0];
}

export async function scrape(article, knownURL, executablePath, allowMPN=false) {
 if(!article||article.length>200)throw new Error('Ungültige Artikelnummer.');
 const browser=await chromium.launch({headless:true,executablePath});
 const deadline=Date.now()+23000;
 try {
  const context=await browser.newContext({locale:'de-DE'});
  // Avoid downloading images/fonts and prevent navigation outside the supplier's sites.
  await context.route('**/*',route=>{
   const request=route.request();
   const url=new URL(request.url());
   const host=url.hostname;
   if(['image','font','media'].includes(request.resourceType()))return route.abort();
   if(url.protocol!=='https:'||!(host==='www.reichelt.de'||host==='www.reichelt.com'||host==='reichelt.de'||host.endsWith('.cdn-reichelt.de')||host==='cdn-reichelt.de'))return route.abort();
   return route.continue();
  });
  const page=await context.newPage();
  async function navigate(url) {
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:Math.max(1,deadline-Date.now())});
   const status=response?.status();
   if([403,429,503].includes(status)||/security check|captcha/i.test(await page.title())) {
    const error=new Error('Reichelt begrenzt oder blockiert den Abruf. Bitte später erneut versuchen; es werden keine Daten geändert.');
    error.status=status||503;throw error;
   }
   if(!response?.ok())throw new Error('Reichelt-Produktseite konnte nicht geladen werden.');
  }
  let url=knownURL;
  if(!allowedProductURL(url)) {
   await navigate('https://www.reichelt.de/de/de/shop/suche?search='+encodeURIComponent(article));
   const direct=await page.locator('.productBuy [itemprop="sku"]').textContent({timeout:500}).catch(()=>'');
   if(direct&&allowedProductURL(page.url()))return await extractProduct(page,article,allowMPN);
   url=await searchProduct(page,article,allowMPN);
   await new Promise(resolve=>setTimeout(resolve,1500));
  }
  await navigate(url);
  return await extractProduct(page,article,allowMPN);
 } finally {await browser.close();}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
 try {
  const data=await scrape(process.argv[2],process.argv[3],process.argv[4],process.argv[5]==='identifier');
  process.stdout.write(JSON.stringify({data}));
 } catch(error) {
  process.stdout.write(JSON.stringify({error:error.message.includes('Timeout')?'Produktdatenabruf hat zu lange gedauert. Bitte später erneut versuchen.':error.message,status:error.status||0}));
  process.exitCode=1;
 }
}
