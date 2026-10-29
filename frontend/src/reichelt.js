export function createReicheltPartUI({api, modal, bind, modalError, esc, label, input, showPart, onSaved}) {
 const markup=()=>`<section class="reichelt-lookup"><h3>Mit Reichelt-Daten anlegen</h3><p class="muted">Artikelnummer oder Herstellerteilenummer eingeben und die gefundenen Daten vor dem Speichern prüfen.</p><form id="reichelt-search">${label('Artikelnummer oder Herstellerteilenummer',input('identifier','','text','required maxlength="200" placeholder="METALL 330 oder MF0207FTE52-330R"'))}<button>Produktdaten abrufen</button><span id="reichelt-progress" role="status" hidden>Daten werden von Reichelt abgerufen …</span></form></section>`;

 function bindLookup(dialog) {
  const form=dialog.querySelector('#reichelt-search');
  if(!form)return;
  bind(form,modalError(async data=>{
   const progress=form.querySelector('#reichelt-progress');
   progress.hidden=false;
   try {
    const proposal=await api('/parts/reichelt/preview','POST',{identifier:data.get('identifier')});
    // A closed dialog must not reopen itself when a slow request completes.
    if(dialog.open&&form.isConnected)preview(proposal);
   } finally {progress.hidden=true;}
  }));
 }

 function preview(proposal) {
  const p=proposal.part;
  const source=`<p><strong>Reichelt-Artikelnummer: ${esc(proposal.article_number)}</strong><br><span class="muted">${proposal.cached?'Zwischengespeicherte Produktdaten':'Produktdaten abgerufen'} · ${new Date(proposal.fetched_at*1000).toLocaleString('de-DE')}</span></p>${proposal.product_url?`<a href="${esc(proposal.product_url)}" target="_blank" rel="noopener noreferrer">Quelle bei Reichelt ansehen ↗</a>`:''}`;
  if(proposal.existing_part){
   const dialog=modal('Reichelt-Artikel bereits vorhanden',`${source}<p>Dieser Artikel ist bereits als <strong>${esc(proposal.existing_part.name)}</strong> angelegt.</p><button id="open-existing-reichelt">Vorhandenes Bauteil öffnen</button><button class="secondary" id="cancel-reichelt">Abbrechen</button>`);
   dialog.querySelector('#open-existing-reichelt').onclick=()=>showPart(proposal.existing_part.id).catch(exception=>{const el=dialog.querySelector('#dialog-error');el.hidden=false;el.textContent=exception.message;});
   dialog.querySelector('#cancel-reichelt').onclick=()=>dialog.close();
   return;
  }
  const dialog=modal('Reichelt-Bauteil prüfen',`${source}<p class="muted">Prüfe die Angaben und ergänze sie bei Bedarf. Beim Speichern werden Bauteil und Reichelt-Lieferantenlink angelegt.</p>${proposal.warnings.length?`<ul class="completion-warnings">${proposal.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`:''}<p>Kategorie: <strong>${esc(proposal.category_name)}</strong></p><form id="reichelt-create" class="form-grid">
   ${label('Bezeichnung *',input('name',p.name,'text','required maxlength="300"'))}
   ${[['manufacturer','Hersteller'],['mpn','Herstellerteilenummer'],['package','Gehäuse / Bauform']].map(([name,title])=>label(title,input(name,p[name],'text','maxlength="200"'))).join('')}
   ${label('Beschreibung',`<textarea name="description">${esc(p.description)}</textarea>`)}${label('Notizen',`<textarea name="notes">${esc(p.notes)}</textarea>`)}
   <fieldset class="full"><legend>Technische Merkmale</legend><div class="form-grid">${proposal.fields.map((field,index)=>label(esc(field.name)+(field.unit?' ('+esc(field.unit)+')':''),input('attr_'+index,p.attributes[field.name]??'',field.type==='number'?'number':'text',field.type==='number'?'step="any"':''))).join('')||'<p class="muted">Keine technischen Merkmale verfügbar.</p>'}</div></fieldset>
   <div class="full manual-review"><label class="check"><input type="checkbox" name="manual_complete" value="1"> Daten von mir vollständig geprüft</label><p class="muted">Das grüne R zeigt die Reichelt-Herkunft. Eigene Änderungen erhalten zusätzlich den orangen Haken; eine vollständige manuelle Prüfung den grünen Haken.</p></div>
   <div class="form-actions full"><button>Bauteil aus Reichelt-Daten anlegen</button><button type="button" class="secondary" id="cancel-reichelt">Abbrechen</button></div></form>`);
  dialog.querySelector('#cancel-reichelt').onclick=()=>dialog.close();
  bind(dialog.querySelector('#reichelt-create'),modalError(async data=>{
   const part=Object.fromEntries([...data].filter(([key])=>!key.startsWith('attr_')&&key!=='manual_complete'));
   part.attributes={};
   proposal.fields.forEach((field,index)=>{const value=data.get('attr_'+index);if(value!=='')part.attributes[field.name]=field.type==='number'?Number(value):value;});
   const saved=await api('/parts/reichelt/create','POST',{token:proposal.token,part,manual_complete:data.get('manual_complete')==='1'});
   dialog.close();
   await onSaved(saved);
  }));
 }

 return {markup, bindLookup};
}
