export function createSettingsUI({api,content,heading,esc,input,label,bind,modal,modalError,onLoggedOut}) {
 async function render(){
  const session=await api('/session');
  content(heading('VERWALTUNG','Einstellungen','Zugangsdaten und lokale Inventardaten verwalten.')+
   `<section class="card settings-section"><h2>Benutzername und Passwort</h2><p class="muted">Für eine Änderung das aktuelle Passwort eingeben. Ein leeres neues Passwort behält das bisherige Passwort bei. Nach dem Speichern bitte neu anmelden.</p><form id="account-form" class="form-grid">${label('Benutzername',input('username',session.username,'text','required maxlength="100" autocomplete="username"'))}${label('Aktuelles Passwort',input('current_password','','password','required autocomplete="current-password"'))}${label('Neues Passwort',input('new_password','','password','minlength="12" autocomplete="new-password"'))}${label('Neues Passwort wiederholen',input('repeat_password','','password','minlength="12" autocomplete="new-password"'))}<small class="full">Ein neues Passwort muss mindestens zwölf Zeichen haben.</small><button class="full">Zugangsdaten speichern</button></form></section>
    <section class="card settings-section"><h2>Datenbank zurücksetzen</h2><p>Entfernt Bauteile, Bestände, Projektlisten, Lagerplätze, Lieferanten und zugehörige Ergänzungsdaten.</p><p><strong>Kategorien mit Hierarchie und technischen Merkmalen sowie dein Konto bleiben erhalten.</strong></p><p class="muted">Vor dem Löschen wird automatisch eine vollständige Sicherung erstellt. Die Vorschau zeigt die betroffenen Daten; nach dem Reset bitte neu anmelden.</p><button class="secondary danger" id="preview-reset">Datenbank zurücksetzen</button></section>`);
  bind(document.querySelector('#account-form'),async data=>{
   if(data.get('new_password')!==data.get('repeat_password'))throw new Error('Die neuen Passwörter stimmen nicht überein.');
   await api('/account','PUT',{username:data.get('username'),current_password:data.get('current_password'),new_password:data.get('new_password')});
   onLoggedOut('Zugangsdaten gespeichert. Bitte mit den neuen Zugangsdaten anmelden.');
  });
  document.querySelector('#preview-reset').onclick=async event=>{
   event.currentTarget.disabled=true;
   try{showReset(await api('/settings/reset/preview','POST',{}));}
   catch(exception){const message=document.querySelector('#message');if(message){message.hidden=false;message.textContent=exception.message;}}
   finally{document.querySelector('#preview-reset')?.removeAttribute('disabled');}
  };
 }
 function showReset(preview){
  const labels={parts:'Bauteile',stocks:'Bestandszeilen',offers:'Lieferantenangebote',locations:'Lagerplätze',suppliers:'Lieferanten',demand_lists:'Projektlisten',demand_items:'Projektpositionen',receipts:'Wareneingänge',curation:'Ergänzungsstatus',product_cache:'Zwischengespeicherte Produktdaten'};
  const dialog=modal('Inventardaten zurücksetzen',`<p><strong>Diese Daten werden nach einer vollständigen Sicherung gelöscht:</strong></p><dl class="reset-summary">${Object.entries(labels).map(([key,name])=>`<div><dt>${name}</dt><dd>${preview.delete[key]}</dd></div>`).join('')}</dl><p class="success">${preview.preserve.categories} Kategorien einschließlich eigener Kategorien und Merkmale sowie dein Konto bleiben erhalten.</p><p class="muted">Alle Sitzungen werden beendet. Für die erneute Anmeldung gelten deine bisherigen Zugangsdaten.</p><form id="reset-form" class="form-grid">${label('Aktuelles Passwort',input('current_password','','password','required autocomplete="current-password"'))}${label('Zur Bestätigung ZURÜCKSETZEN eingeben',input('confirmation','','text','required autocomplete="off" spellcheck="false"'))}<div class="form-actions full"><button class="danger secondary" disabled>Inventardaten endgültig löschen</button><button class="secondary" id="cancel-reset" type="button">Abbrechen</button></div></form>`);
  const form=dialog.querySelector('#reset-form'),submit=form.querySelector('button:not([type])');
  form.addEventListener('input',()=>{submit.disabled=form.elements.confirmation.value!=='ZURÜCKSETZEN'||!form.elements.current_password.value;});
  dialog.querySelector('#cancel-reset').onclick=()=>dialog.close();
  bind(form,modalError(async data=>{
   const result=await api('/settings/reset','POST',{token:preview.token,current_password:data.get('current_password'),confirmation:data.get('confirmation')});
   dialog.close();
   onLoggedOut('Inventardaten zurückgesetzt. Kategorien und Konto erhalten. Sicherung: '+result.backup+'. Bitte neu anmelden.');
  }));
 }
 return {render};
}
