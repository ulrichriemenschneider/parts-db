// Public shop categories only. A resumable, serial crawl of category pages and
// the official XML sitemaps; no product crawl, private API or challenge solving.
import {chromium} from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';

const output=process.argv[2]||'/tmp/partsdb-reichelt-categories.json';
let state;
try{state=JSON.parse(await fs.readFile(output,'utf8'));}catch{state={started_at:new Date().toISOString(),nodes:{},queue:[],visited:[],sitemap_urls:[],sitemaps:[],sources:[]};}
const browser=await chromium.launch({headless:true,executablePath:process.env.REICHELT_BROWSER_PATH||'/usr/bin/chromium'});
const page=await browser.newPage({locale:'de-DE'});
await page.route('**/*',route=>{
 const url=new URL(route.request().url());
 if(route.request().resourceType()!=='document'||url.protocol!=='https:'||url.hostname!=='www.reichelt.de')return route.abort();
 return route.continue();
});
const categoryId=url=>Number(new URL(url).pathname.match(/\/shop\/kategorie\/[^/]+-(\d+)$/)?.[1])||null;
const save=()=>fs.writeFile(output,JSON.stringify(state,null,2)+'\n');
function schedule(url){if(!state.visited.includes(url)&&!state.queue.includes(url))state.queue.push(url);}
function add(node){
 const previous=state.nodes[node.id];
 // A breadcrumb is the canonical parent, even if a category is also linked
 // from another group or directly from the global menu.
 state.nodes[node.id]={...previous,...node};
}
async function navigate(url){
 const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
 if(!response?.ok()||/security check|captcha/i.test(await page.title()))throw new Error('Abruf gestoppt: '+response?.status()+' '+url);
 return response;
}
try{
 if(!state.sitemaps_complete){
  const response=await navigate('https://www.reichelt.de/sitemap.xml');
  const xml=await response.text();
  const sitemaps=[...xml.matchAll(/<loc>(https:\/\/www\.reichelt\.de\/sitemaps\/categories\/[^<]+)<\/loc>/g)].map(m=>m[1]);
  if(!sitemaps.length)throw new Error('Keine offiziellen Kategorie-Sitemaps gefunden.');
  for(const url of sitemaps){
   if(state.sitemaps.some(sitemap=>sitemap.url===url))continue;
   await page.waitForTimeout(1000);
   const response=await navigate(url),xml=await response.text();
   const urls=[...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>m[1].replaceAll('&amp;','&')).filter(categoryId);
   if(!urls.length)throw new Error('Leere Kategorie-Sitemap: '+url);
   state.sitemaps.push({url,count:urls.length});state.sitemap_urls.push(...urls);schedule(urls[0]);
   await save();
  }
  state.sitemaps_complete=true;
  await save();
 }
 if(!state.sources.length){
  await navigate('https://www.reichelt.de/de/de/');
  const urls=await page.locator('nav a.rootgroups').evaluateAll(links=>links.map(a=>a.href));
  if(!urls.length)throw new Error('Shop-Hauptgruppen fehlen.');
  state.sources=urls;urls.forEach(schedule);await save();
 }
 let requests=0;
 while(true){
  if(!state.queue.length){
   // Sitemaps cover additional published categories outside the main menu.
   const missing=state.sitemap_urls.filter(url=>!state.nodes[categoryId(url)]);
   if(!missing.length)break;
   missing.forEach(schedule);
  }
  const url=state.queue[0];
  await page.waitForTimeout(1000);
  await navigate(url);
  const data=await page.evaluate(()=>{
   const clean=value=>value.replace(/\s+/g,' ').trim();
   const node=link=>{
    const url=new URL(link.href),match=url.pathname.match(/\/shop\/kategorie\/[^/]+-(\d+)$/);
    return match?{id:Number(match[1]),name:clean(link.querySelector('[itemprop=name]')?.textContent||link.textContent),url:url.origin+url.pathname}:null;
   };
   const crumbs=[...document.querySelectorAll('#breadcrumb [itemprop=item]')].map(node).filter(Boolean);
   const children=[...document.querySelectorAll('a.category__headline')].map(link=>{
    const child=node(link),cta=link.closest('.category')?.querySelector('.category__cta')?.textContent||'';
    return child?{...child,branch:/\d+\s+Gruppen/i.test(cta),group_count:Number(cta.match(/(\d+)\s+Gruppen/i)?.[1])||0}:null;
   }).filter(Boolean);
   return {crumbs,children,title:clean(document.querySelector('h1')?.textContent||''),url:location.href};
  });
  const id=categoryId(data.url)||categoryId(url);
  if(!id||!data.crumbs.some(node=>node.id===id))throw new Error('Kategoriepfad fehlt: '+url);
  let parent_id=null;
  for(const node of data.crumbs){add({...node,parent_id,canonical:true});parent_id=node.id;}
  const current=state.nodes[id];
  if(data.title)current.page_title=data.title;
  current.checked=true;current.child_ids=data.children.map(child=>child.id);
  for(const child of data.children){
   if(!state.nodes[child.id]?.canonical)add({...child,parent_id:id});
   if(child.branch)schedule(child.url);
  }
  if(current.branch&&current.group_count&&!data.children.length)throw new Error('Untergruppen konnten nicht gelesen werden: '+url);
  state.visited.push(url);state.queue.shift();requests++;state.updated_at=new Date().toISOString();
  await save();
  if(requests%10===0)console.log(JSON.stringify({requests:state.visited.length,categories:Object.keys(state.nodes).length,pending:state.queue.length,sitemap_missing:state.sitemap_urls.filter(url=>!state.nodes[categoryId(url)]).length}));
 }
 state.completed_at=new Date().toISOString();state.sitemap_missing=[];delete state.last_error;await save();
 console.log('Vollständig:',Object.keys(state.nodes).length,'Kategorien;',state.visited.length,'Gruppenseiten;',output);
}catch(error){state.last_error=error.message;await save();console.error(error.message);process.exitCode=1;}
finally{await browser.close();}
