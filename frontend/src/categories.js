export function enhanceCategorySelects(container) {
 for(const select of container.querySelectorAll('select[data-category-search]')){
  if(select.dataset.enhanced||select.disabled)continue;
  select.dataset.enhanced='yes';
  const all=[...select.options].map(option=>({value:option.value,text:option.textContent}));
  const search=document.createElement('input');
  search.type='search';search.placeholder='Kategorien nach Name oder Pfad eingrenzen …';
  search.setAttribute('aria-label','Kategorien eingrenzen');
  search.className='category-select-search';
  const label=select.closest('label');
  if(label){
   const wrapper=document.createElement('div');wrapper.className='category-selector';
   label.before(wrapper);wrapper.append(search,label);
  }else select.before(search);
  search.addEventListener('input',()=>{
   const selected=select.value,query=search.value.trim().toLocaleLowerCase('de');
   const matches=all.filter(option=>!option.value||option.value===selected||option.text.toLocaleLowerCase('de').includes(query));
   select.replaceChildren(...matches.map(item=>new Option(item.text,item.value,false,item.value===selected)));
   select.value=selected;
  });
 }
}

export function createCategoryUI({catalogs,content,heading,esc,edit}) {
 let parent=null,query='',page=1;
 const pageSize=25;
 function draw(){
  const all=catalogs().categories,byId=new Map(all.map(item=>[item.id,item]));
  const children=new Map();
  all.forEach(item=>{const key=item.parent_id??null;if(!children.has(key))children.set(key,[]);children.get(key).push(item);});
  const terms=query.trim().toLocaleLowerCase('de').split(/\s+/).filter(Boolean);
  const rows=terms.length?all.filter(item=>terms.every(term=>item.name.toLocaleLowerCase('de').includes(term))):(children.get(parent)||[]);
  const pages=Math.max(1,Math.ceil(rows.length/pageSize));page=Math.min(page,pages);
  const trail=[];let ancestor=byId.get(parent);const seen=new Set();
  while(ancestor&&!seen.has(ancestor.id)){seen.add(ancestor.id);trail.unshift(ancestor);ancestor=byId.get(ancestor.parent_id);}
  const imported=all.filter(item=>item.reichelt_id).length;
  content(heading('VERWALTUNG','Kategorien',`${imported} Reichelt-Kategorien mit vollständigen Pfaden. Technische Merkmale können je Kategorie gepflegt werden.`,'<button id="new-managed">+ Neu anlegen</button>')+
   `<form id="category-search" class="filters"><label>Kategorien durchsuchen<input type="search" name="q" value="${esc(query)}" placeholder="Zum Beispiel Widerstände, Sensoren oder Labornetzgeräte"></label><button>Suchen</button></form><div class="category-breadcrumb" aria-label="Kategoriepfad"><button class="quiet" data-category-parent="">Alle Kategorien</button>${trail.map(item=>`<span aria-hidden="true">›</span><button class="quiet" data-category-parent="${item.id}">${esc(item.label)}</button>`).join('')}</div>
   <div class="list-meta"><strong role="status">${rows.length} ${terms.length?'Treffer im gesamten Kategorienbaum':parent?'Unterkategorien':'Hauptkategorien und eigene Kategorien'}</strong><span>KATEGORIENLISTE</span></div>
   ${rows.length?`<div class="table-wrap category-table"><table><colgroup><col><col class="category-source"><col class="category-fields"><col class="category-children"><col class="category-edit"></colgroup><thead><tr><th>Kategorie / Pfad</th><th>Quelle</th><th>Merkmale</th><th>Unterkategorien</th><th></th></tr></thead><tbody>${rows.slice((page-1)*pageSize,page*pageSize).map(item=>{
    const count=children.get(item.id)?.length||0;
    return `<tr data-category-row="${item.id}"><td><strong><button type="button" class="category-name" ${count?`data-category-parent="${item.id}"`:`data-managed="${item.id}"`} title="${count?'Unterkategorien öffnen':'Kategorie bearbeiten'}">${esc(item.label)}</button></strong>${item.name!==item.label?`<small class="category-path">${esc(item.name)}</small>`:''}</td><td data-caption="Quelle">${item.source_url?`<a class="chip category-source-link" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer" title="Kategorie bei Reichelt ansehen">Reichelt ↗</a>`:'<span class="chip">Eigene Kategorie</span>'}</td><td data-caption="Merkmale">${item.fields.length}</td><td data-caption="Unterkategorien">${count?`<button type="button" class="quiet quantity" data-category-parent="${item.id}" aria-label="Unterkategorien öffnen">${count} ↗</button>`:'0'}</td><td><button class="quiet" data-managed="${item.id}">Bearbeiten</button></td></tr>`;
   }).join('')}</tbody></table></div>`:'<div class="empty"><h2>Keine passenden Kategorien gefunden.</h2><p>Passe den Suchbegriff an oder gehe zu einer übergeordneten Kategorie.</p></div>'}
   <div class="pagination"><button class="secondary" id="categories-prev" ${page===1?'disabled':''}>← Zurück</button><span>Seite ${page} / ${pages}</span><button class="secondary" id="categories-next" ${page===pages?'disabled':''}>Weiter →</button></div>`);
  document.querySelector('#new-managed').onclick=()=>edit();
  document.querySelector('#category-search').onsubmit=event=>{event.preventDefault();query=new FormData(event.currentTarget).get('q');page=1;draw();};
  document.querySelectorAll('[data-category-parent]').forEach(button=>button.onclick=()=>{parent=button.dataset.categoryParent?Number(button.dataset.categoryParent):null;query='';page=1;draw();});
  document.querySelectorAll('[data-managed]').forEach(button=>button.onclick=()=>edit(byId.get(Number(button.dataset.managed))));
  document.querySelector('#categories-prev').onclick=()=>{page--;draw();};
  document.querySelector('#categories-next').onclick=()=>{page++;draw();};
 }
 return {render:()=>{parent=null;query='';page=1;draw();}};
}
