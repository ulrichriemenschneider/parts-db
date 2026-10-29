import { curationBadges } from './curation.js';
import { enhanceCategorySelects } from './categories.js';
import { renderOverview } from './overview.js';
export function createDemandUI(ui) {
 const {api, esc, options, input, label, bind, content, heading, error, modal, modalError, catalogs, loadCatalogs, showPart, navigate} = ui;
 const date = value => new Date(value*1000).toLocaleDateString('de-DE');
 const status = list => list.received === list.quantity ? 'Vollständig erhalten' : list.received ? 'Teilweise erhalten' : 'Noch kein Wareneingang';
 const overviewState={query:'',page:1};

 async function list(reset=false) {
  if(reset){overviewState.query='';overviewState.page=1;}
  const lists = await api('/demands');
  renderOverview({content,heading,esc,kicker:'PLANEN & EINLAGERN',title:'Projektbedarf',
   description:'Reichelt-Listen sammeln und Lieferungen nach und nach einbuchen.',
   createButton:'<button id="new-demand">+ Reichelt-Liste importieren</button>',items:lists,state:overviewState,
   searchLabel:'Projektlisten durchsuchen',searchText:item=>[item.name,item.source_filename,status(item)].join(' '),
   countLabel:'Projektlisten',listLabel:'PROJEKTBEDARF',tableClass:'project-list-table',
   emptyTitle:'Noch keine Projektlisten.',emptyDescription:'Importiere einen Reichelt-Listenexport als Projektbedarf. Der Bestand bleibt beim Import unverändert.',
   columns:[{label:'Projekt / Quelldatei'},{label:'Status',className:'overview-status'},{label:'Positionen',className:'overview-count'},{label:'Erhalten / geplant',className:'overview-amount'},{label:'Importiert',className:'overview-date'},{label:'',className:'overview-action'}],
   renderRow:item=>`<tr data-demand-row="${item.id}"><td><strong><button type="button" class="demand-name" data-demand="${item.id}">${esc(item.name)}</button></strong><small>${esc(item.source_filename)}</small></td><td data-caption="Status"><span class="chip">${esc(status(item))}</span></td><td data-caption="Positionen">${item.positions}</td><td data-caption="Erhalten / geplant"><span class="quantity">${item.received} / ${item.quantity}</span></td><td data-caption="Importiert">${date(item.imported_at)}</td><td><button class="quiet" data-demand="${item.id}">Liste öffnen</button></td></tr>`,
   bindRows:target=>target.querySelectorAll('[data-demand]').forEach(button=>button.onclick=()=>detail(Number(button.dataset.demand)).catch(error))});
  document.querySelector('#new-demand').onclick = importView;
 }

 function importView() {
  content(heading('REICHELT-LISTE', 'Projektbedarf importieren', 'Artikelnummer und Listenmenge werden übernommen. Es wird noch kein Lagerbestand gebucht.')+
   `<form id="demand-import" class="card form-grid">${label('Projektname', input('project_name','','text','maxlength="200" placeholder="Optional – sonst Dateiname"'))}${label('Reichelt-CSV-Datei','<input name="file" type="file" accept=".csv,text/csv" required>')}<p class="full muted">Originalexport ohne Kopfzeile: Artikelnummer;Menge;optionaler Zusatz. Doppelte Artikel werden zusammengefasst.</p><button class="full">Datei prüfen</button></form><div id="demand-preview"></div>`);
  bind(document.querySelector('#demand-import'), async form=>{
   const result = await api('/demands/import','POST',form);
   await preview(result, document.querySelector('#demand-preview'));
  });
 }

 async function preview(data, target) {
  // Draft edits stay local until the staged server preview is explicitly applied.
  const drafts = new Map();
  function remember() {
   data.items.forEach(item=>drafts.set(item.index, {
    name: target.querySelector(`[name="demand-name-${item.index}"]`).value,
    category_id: Number(target.querySelector(`[name="demand-category-${item.index}"]`).value)
   }));
  }
  function renderPreview() {
   target.innerHTML = `<article class="card demand-preview"><h2>Reichelt-Importvorschau</h2><p>${data.items.length} Positionen · ${data.items.reduce((sum,item)=>sum+item.quantity,0)} Stück Projektbedarf</p><p class="muted">Neue Bauteile und Reichelt-Angebote werden angelegt. Vorhandene Bauteile bleiben unverändert. Es erfolgt noch keine Einlagerung.</p>
    <p class="muted">${data.enrichment_available?'Produktdaten können je neuer Position optional abgerufen werden. Vorschläge vor dem Import prüfen; API-Abfragelimits gelten.':'Optionale Produktdatenabfrage ist nicht eingerichtet. Du kannst die Liste ohne sie importieren und Bauteile später ergänzen.'}</p>
    <form id="apply-demand">${label('Projektname',input('name',data.name,'text','required maxlength="200"'))}<div class="demand-import-items">${data.items.map(item=>{
     const draft = drafts.get(item.index)||item;
     return `<section class="demand-import-item" data-preview-item="${item.index}"><div class="demand-item-title"><strong>${esc(item.article_number)}</strong><span class="chip">${item.quantity} Stück · ${item.part_id?'Vorhandenes Bauteil':item.enriched?'Produktdaten ergänzt':'Neues Bauteil'}</span></div><div class="form-grid">${label('Bezeichnung '+esc(item.article_number),input('demand-name-'+item.index,draft.name,'text',`required maxlength="300" ${item.part_id?'disabled':''}`))}${label('Kategorie '+esc(item.article_number),`<select data-category-search name="demand-category-${item.index}" required ${item.part_id?'disabled':''}>${options(catalogs().categories,draft.category_id)}</select>`)}</div>${item.note?`<p class="preserve muted">${esc(item.note)}</p>`:''}
      ${item.enriched?`<p>${esc(item.manufacturer)} ${esc(item.mpn)} ${esc(item.package)}</p><p class="preserve muted">${esc(item.description)}</p>${item.product_url?`<a href="${esc(item.product_url)}" target="_blank" rel="noopener noreferrer">Produkt ansehen ↗</a>`:''}<p>${Object.entries(item.suggested_attributes).map(([name,value])=>`${esc(name)}: ${esc(value)} ${esc({Widerstand:'Ω',Toleranz:'%',Kapazität:'µF',Spannungsfestigkeit:'V'}[name]||'')}`).join(' · ')}</p>`:''}
      <button type="button" class="secondary" data-enrich="${item.index}" ${!data.enrichment_available||item.part_id?'disabled':''}>Produktdaten ergänzen</button><p class="muted" data-enrich-status="${item.index}" role="status"></p></section>`;
    }).join('')}</div><button>Als Projektbedarf übernehmen</button></form></article>`;
   enhanceCategorySelects(target);
   target.querySelectorAll('[data-enrich]').forEach(button=>button.onclick=async()=>{
    remember();
    data.name = target.querySelector('[name=name]').value;
    const index = Number(button.dataset.enrich);
    const message = target.querySelector(`[data-enrich-status="${index}"]`);
    button.disabled = true;
    message.textContent = 'Produktdaten werden abgerufen …';
    target.querySelector('#apply-demand button:not([type])').disabled = true;
    // Only one staged suggestion is fetched at a time; all other edits are retained.
    target.querySelectorAll('[data-enrich]').forEach(element=>element.disabled=true);
    try {
     const result = await api('/demands/import/enrich','POST',{token:data.token,index});
     result.name = data.name;
     data = result;
     drafts.delete(index);
     renderPreview();
    } catch(exception) {
     renderPreview();
     target.querySelector(`[data-enrich-status="${index}"]`).textContent = exception.message;
    }
   });
   bind(target.querySelector('#apply-demand'),async form=>{
    remember();
    const result = await api('/demands/import','POST',{
     token:data.token, name:form.get('name'), items:data.items.map(item=>({index:item.index,...drafts.get(item.index)}))
    });
    await loadCatalogs();
    await navigate(result.id);
   });
  }
  renderPreview();
 }

 function articleCell(item) {
  return `<strong class="demand-article-name">${esc(item.part.name)} ${curationBadges(item.part.curation)}</strong><small class="demand-part-name">${esc(item.article_number)}</small><small>${esc(catalogs().categories.find(c=>c.id===item.part.category_id)?.name)}${Object.keys(item.part.attributes).length?' · ':''}${Object.entries(item.part.attributes).map(([name,value])=>`${esc(name)}: ${esc(value)} ${esc(catalogs().categories.find(c=>c.id===item.part.category_id)?.fields.find(f=>f.name===name)?.unit||'')}`).join(' · ')}</small>${item.note?`<small class="preserve">${esc(item.note)}</small>`:''}`;
 }

 async function detail(id, notice='') {
  await loadCatalogs();
  const demand = await api('/demands/'+id);
  const open = demand.items.filter(item=>item.remaining>0);
  content(heading('PROJEKTBEDARF',esc(demand.name),`${esc(status(demand))} · ${demand.received} / ${demand.quantity} Stück erhalten`, '<div class="demand-heading-actions"><button class="secondary" id="rename-demand">Name ändern</button><button class="secondary" id="back-demands">← Projektlisten</button></div>')+
   `<p class="success" id="demand-notice" role="status" ${notice?'':'hidden'}>${esc(notice)}</p><p class="muted demand-source">Quelle: ${esc(demand.source_filename)} · Import vom ${date(demand.imported_at)}</p>
    <section class="bulk-enrichment" aria-label="Liste automatisch vervollständigen"><div class="bulk-tools"><button id="complete-all" ${demand.product_enrichment_available?'':'disabled'}>Alle Daten vervollständigen</button><button class="secondary" id="stop-completion" hidden>Stoppen</button></div><p class="muted">Ergänzt fehlende Angaben aller Positionen direkt aus Reichelt-Daten, ohne Prüfdialog. Vorhandene eigene Werte bleiben erhalten. Die Liste während des Laufs geöffnet lassen.</p><p id="bulk-status" role="status" hidden></p><progress id="bulk-progress" aria-label="Fortschritt der Datenvervollständigung" max="${demand.items.length||1}" value="0" hidden></progress><details id="bulk-results" hidden><summary>Ergebnisse und Hinweise</summary><ul></ul></details></section>
    <p class="curation-legend"><span class="curation-mark reichelt" aria-hidden="true">R</span> Reichelt-Daten · <span class="curation-mark manual-partial" aria-hidden="true">✓</span> teilweise manuell · <span class="curation-mark manual-complete" aria-hidden="true">✓</span> vollständig manuell geprüft</p><div class="table-wrap demand-table"><table><colgroup><col><col class="demand-number"><col class="demand-number"><col class="demand-number"><col class="demand-actions"></colgroup><thead><tr><th>Artikel / Bauteil</th><th>Geplant</th><th>Erhalten</th><th>Offen</th><th></th></tr></thead><tbody>${demand.items.map(item=>`<tr><td data-demand-cell="${item.id}">${articleCell(item)}</td><td data-caption="Geplant">${item.quantity}</td><td data-caption="Erhalten">${item.received}</td><td data-caption="Offen">${item.remaining}</td><td><div class="demand-row-actions"><button class="quiet" data-demand-part="${item.part_id}">Bauteil öffnen</button><button class="secondary" data-complete="${item.id}" ${demand.product_enrichment_available?'':'disabled title="Browser-Scraper auf dem Backend einrichten"'}>Daten vervollständigen</button></div></td></tr>`).join('')}</tbody></table></div>
    <section class="card receipt-card"><h2>Wareneingang buchen</h2><p class="muted">Wähle die gelieferten Positionen und passe die Mengen an. Teilmengen bleiben für eine spätere Lieferung offen.</p>${open.length?`
     ${catalogs().locations.length?'':'<p class="receipt-warning">Bitte zuerst unter Lagerplätze einen Lagerplatz anlegen und diese Liste erneut öffnen.</p>'}
     <form id="receipt"><div class="receipt-toolbar">${label('Gemeinsamer Lagerplatz',`<select id="receipt-location">${options(catalogs().locations,'','Bitte wählen')}</select>`)}<button type="button" class="secondary" id="select-open">Alle offenen auswählen</button><button type="button" class="secondary" id="select-none">Auswahl aufheben</button></div>
      <div class="receipt-items">${open.map(item=>`<div class="receipt-item" data-receipt-item="${item.id}"><label class="check receipt-select"><input type="checkbox" name="selected-${item.id}" checked> ${esc(item.article_number)}</label><p class="muted receipt-open">${item.remaining} von ${item.quantity} Stück offen</p>${label('Eingangsmenge '+esc(item.article_number),input('quantity-'+item.id,item.remaining,'number',`required min="1" max="${item.remaining}" step="1"`))}${label('Lagerplatz '+esc(item.article_number),`<select name="location-${item.id}" required>${options(catalogs().locations)}</select>`)}</div>`).join('')}</div>
      <p id="receipt-summary" aria-live="polite"></p><button ${catalogs().locations.length?'':'disabled'}>Wareneingang verbindlich buchen</button><button type="button" class="secondary" id="reload-demand">Liste neu laden</button>
     </form>`:'<p class="success">Alle Positionen sind vollständig erhalten.</p>'}</section>
     <div class="form-actions"><button class="quiet danger" id="delete-demand">Bedarfsliste löschen</button></div>`);
  bindBulkCompletion(demand);
  document.querySelector('#back-demands').onclick = ()=>list().catch(error);
  const renameButton=document.querySelector('#rename-demand');
  renameButton.onclick=()=>{
   const dialog=modal('Bedarfsliste umbenennen',`<form id="rename-demand-form">${label('Listenname',input('name',demand.name,'text','required maxlength="200"'))}<div class="form-actions"><button>Namen speichern</button><button type="button" class="secondary" id="cancel-rename">Abbrechen</button></div></form>`);
   const form=dialog.querySelector('#rename-demand-form');
   form.elements.name.focus();form.elements.name.select();
   dialog.querySelector('#cancel-rename').onclick=()=>dialog.close();
   bind(form,modalError(async data=>{
    const name=data.get('name').trim();
    if(name===demand.name){dialog.close();return;}
    const saved=await api('/demands/'+id,'PUT',{name});
    if(document.querySelector('#rename-demand')!==renameButton)return;
    if(form.isConnected)dialog.close();
    if(saved.version!==demand.version+1){await detail(id,'Listenname gespeichert. Die zwischenzeitlich geänderte Liste wurde neu geladen.');return;}
    // A rename alone keeps the user's unbooked receipt selection and quantities.
    demand.name=saved.name;demand.version=saved.version;
    document.querySelector('#content h1').textContent=saved.name;
    const message=document.querySelector('#demand-notice');
    message.textContent='Listenname gespeichert.';message.hidden=false;
   }));
  };
  document.querySelectorAll('[data-demand-part]').forEach(button=>button.onclick=()=>showPart(Number(button.dataset.demandPart)).catch(error));
  document.querySelectorAll('[data-complete]').forEach(button=>button.onclick=async()=>{
   document.querySelector('#message').hidden=true;
   const buttons=[...document.querySelectorAll('[data-complete]')];
   buttons.forEach(element=>element.disabled=true);
   button.textContent='Daten werden abgerufen …';
   try {
    const proposal=await api('/demands/'+id+'/enrich','POST',{item_id:Number(button.dataset.complete)});
    completionPreview(id,proposal);
   } catch(exception) {error(exception);}
   finally {buttons.forEach(element=>{element.disabled=false;element.textContent='Daten vervollständigen';});}
  });
  document.querySelector('#delete-demand').onclick = async()=>{
   if (!confirm('Bedarfsliste löschen? Bereits gebuchte Bestände und Bauteile bleiben erhalten.')) return;
   try { await api('/demands/'+id+'?confirm=yes','DELETE'); await list(); } catch(exception) { error(exception); }
  };
  if (!open.length) return;
  const form = document.querySelector('#receipt');
  const requestId = crypto.randomUUID();
  function selection() {
   return open.filter(item=>form.elements['selected-'+item.id].checked);
  }
  function updateSelection() {
   for (const item of open) {
    const checked = form.elements['selected-'+item.id].checked;
    form.elements['quantity-'+item.id].disabled = !checked;
    form.elements['location-'+item.id].disabled = !checked;
    if(checked&&!form.elements['location-'+item.id].value&&document.querySelector('#receipt-location').value)form.elements['location-'+item.id].value=document.querySelector('#receipt-location').value;
   }
   const selected = selection();
   const total = selected.reduce((sum,item)=>sum+Number(form.elements['quantity-'+item.id].value||0),0);
   document.querySelector('#receipt-summary').textContent = `${selected.length} Positionen ausgewählt · ${total} Stück werden zusätzlich eingelagert.`;
   form.querySelector('button:not([type])').disabled = !selected.length||!catalogs().locations.length;
  }
  document.querySelector('#receipt-location').onchange = event=>{
   open.forEach(item=>{if(form.elements['selected-'+item.id].checked)form.elements['location-'+item.id].value=event.target.value;});
  };
  form.addEventListener('input',updateSelection);
  document.querySelector('#select-open').onclick = ()=>{open.forEach(item=>form.elements['selected-'+item.id].checked=true);updateSelection();};
  document.querySelector('#select-none').onclick = ()=>{open.forEach(item=>form.elements['selected-'+item.id].checked=false);updateSelection();};
  document.querySelector('#reload-demand').onclick = ()=>detail(id).catch(error);
  bind(form, async()=>{
   const items = selection().map(item=>({item_id:item.id,quantity:Number(form.elements['quantity-'+item.id].value),location_id:Number(form.elements['location-'+item.id].value)}));
   await api('/demands/'+id+'/receive','POST',{version:demand.version,request_id:requestId,items});
   await detail(id,'Wareneingang erfolgreich gebucht. Offene Mengen wurden aktualisiert.');
  });
  updateSelection();
 }
 function bindBulkCompletion(demand) {
  const panel=document.querySelector('.bulk-enrichment');
  const button=panel.querySelector('#complete-all'),stop=panel.querySelector('#stop-completion');
  const message=panel.querySelector('#bulk-status'),progress=panel.querySelector('#bulk-progress');
  const results=panel.querySelector('#bulk-results'),entries=results.querySelector('ul');
  let running=false,stopped=false;
  const alive=()=>panel.isConnected&&!stopped;
  async function pause(milliseconds){
   const until=Date.now()+milliseconds;
   while(alive()&&Date.now()<until)await new Promise(resolve=>setTimeout(resolve,Math.min(250,until-Date.now())));
  }
  function result(item,text,failed=false){
   const entry=document.createElement('li');entry.textContent=item.article_number+': '+text;
   if(failed)entry.className='bulk-error';
   entries.append(entry);results.hidden=false;
  }
  stop.onclick=()=>{stopped=true;stop.disabled=true;message.textContent='Wird nach dem laufenden Artikel gestoppt …';};
  button.onclick=async()=>{
   if(running)return;
   running=true;stopped=false;button.disabled=true;stop.hidden=false;stop.disabled=false;
   entries.replaceChildren();results.hidden=true;message.hidden=false;progress.hidden=false;progress.value=0;
   const controls=[...document.querySelectorAll('[data-complete],[data-demand-part],#rename-demand,#delete-demand')];
   const disabled=controls.map(control=>control.disabled);controls.forEach(control=>control.disabled=true);
   let done=0,succeeded=0,failed=0,halted='';
   try {
    for(const item of demand.items){
     if(!alive())break;
     message.textContent=`${done} / ${demand.items.length} verarbeitet · ${item.article_number} wird abgerufen …`;
     let response,failure,retries=0;
     while(alive()){
      try {response=await api('/demands/'+demand.id+'/enrich/auto','POST',{item_id:item.id});break;}
      catch(exception){
       if(exception.status===429&&!exception.blocked&&retries++<10){
        message.textContent=`${done} / ${demand.items.length} verarbeitet · kurze Abrufpause, danach geht es automatisch weiter …`;
        await pause(Math.max(1,exception.retryAfter||3)*1000);continue;
       }
       failure=exception;break;
      }
     }
     if(!panel.isConnected)break;
     if(!response&&!failure)break;
     if(failure){
      failed++;result(item,failure.message,true);
      if(failure.blocked||!failure.status||[401,403,404,429].includes(failure.status))halted=failure.message;
     }else{
      succeeded++;
      const category=catalogs().categories.find(category=>category.id===response.category.id);
      if(category)Object.assign(category,response.category);
      for(const linked of demand.items.filter(linked=>linked.part_id===item.part_id)){
       linked.part=response.part;
       const cell=document.querySelector(`[data-demand-cell="${linked.id}"]`);
       if(cell)cell.innerHTML=articleCell(linked);
      }
      result(item,(response.changed.length?response.changed.length+' Angaben ergänzt.':'Abgeglichen; keine fehlenden Angaben.')+(response.warnings.length?' Hinweise: '+response.warnings.join(' '):''));
     }
     done++;progress.value=done;
     if(halted)break;
     message.textContent=`${done} / ${demand.items.length} verarbeitet · ${succeeded} erfolgreich, ${failed} Fehler`;
     if(done<demand.items.length&&(failure||!response.cached))await pause(3100);
    }
   }catch(exception){halted=exception.message;}
   finally {
    running=false;
    if(panel.isConnected){
     button.disabled=!demand.product_enrichment_available;stop.hidden=true;
     controls.forEach((control,index)=>control.disabled=disabled[index]);
     message.textContent=`${stopped||halted?'Gestoppt':'Abgeschlossen'}: ${done} / ${demand.items.length} verarbeitet · ${succeeded} erfolgreich, ${failed} Fehler.${halted?' '+halted:''}`;
    }
   }
  };
 }

 function completionPreview(id,proposal) {
  const display=value=>esc(value===null||value===undefined||value===''?'—':value);
  const dialog=modal('Produktdaten prüfen',`<p><strong>${esc(proposal.article_number)}</strong></p>
   <p class="muted">${proposal.cached?'Zwischengespeicherte Produktdaten':'Produktdaten abgerufen'} · ${new Date(proposal.fetched_at*1000).toLocaleString('de-DE')}</p>
   ${proposal.source_url?`<a href="${esc(proposal.source_url)}" target="_blank" rel="noopener noreferrer">Quelle bei Reichelt ansehen ↗</a>`:''}
   <p class="muted">Wähle die Änderungen aus. Vorhandene Angaben werden nur ersetzt, wenn du die Änderung ausdrücklich auswählst. Kategorie und technische Merkmale gelten auch für dieses Bauteil in anderen Projekten. Bestände und Bedarfsmengen bleiben unverändert.</p>
   ${proposal.warnings.length?`<ul class="completion-warnings">${proposal.warnings.map(warning=>`<li>${esc(warning)}</li>`).join('')}</ul>`:''}
   ${proposal.changes.length?`<form id="complete-part"><div class="table-wrap completion-table"><table><thead><tr><th>Übernehmen</th><th>Merkmal</th><th>Bisher</th><th>Vorschlag</th></tr></thead><tbody>${proposal.changes.map(change=>`<tr><td><input type="checkbox" name="selected" value="${esc(change.key)}" aria-label="${esc(change.label)} übernehmen" ${change.selected?'checked':''} ${change.allowed?'':'disabled'}></td><td>${esc(change.label)}${change.reason?`<small>${esc(change.reason)}</small>`:''}</td><td class="preserve">${display(change.before)} ${change.before!==null?esc(change.unit):''}</td><td class="preserve">${display(change.after)} ${esc(change.unit)}</td></tr>`).join('')}</tbody></table></div><div class="form-actions"><button>Ausgewählte Änderungen speichern</button><button type="button" class="secondary" id="cancel-completion">Abbrechen</button></div></form>`:'<p class="success">Die verfügbaren Produktdaten stimmen bereits überein.</p><button id="confirm-reichelt">Reichelt-Abgleich bestätigen</button>'}`);
  const form=document.querySelector('#complete-part');
  if(!form){
   const button=document.querySelector('#confirm-reichelt');
   button.onclick=async()=>{
    button.disabled=true;
    try{await api('/demands/'+id+'/enrich/apply','POST',{token:proposal.token,selected:[]});dialog.close();await detail(id,'Reichelt-Abgleich bestätigt.');}
    catch(exception){const message=dialog.querySelector('#dialog-error');message.hidden=false;message.textContent=exception.message;button.disabled=false;}
   };
   return;
  }
  document.querySelector('#cancel-completion').onclick=()=>dialog.close();
  const update=()=>{form.querySelector('button:not([type])').disabled=!form.querySelector('[name=selected]:checked:not(:disabled)');};
  form.addEventListener('change',update);update();
  bind(form,modalError(async data=>{
   await api('/demands/'+id+'/enrich/apply','POST',{token:proposal.token,selected:data.getAll('selected')});
   dialog.close();
   await detail(id,'Produktinformationen wurden ergänzt. Bestände und Bedarfsmengen bleiben unverändert.');
  }));
 }
 return {list, detail, preview, importView};
}
