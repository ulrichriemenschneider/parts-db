// Shared search and pagination for the project, location and supplier lists.
export function renderOverview({content,heading,esc,kicker,title,description,createButton,items,state,
 searchLabel,searchText,countLabel,listLabel,columns,renderRow,bindRows,tableClass='',emptyTitle,emptyDescription}) {
 const pageSize=25;
 content(heading(kicker,title,description,createButton)+`<form id="overview-search" class="filters list-search"><label>${esc(searchLabel)}<input type="search" name="q" value="${esc(state.query)}" placeholder="Name oder weitere Angaben"></label><button>Suchen</button></form><div id="overview-results" aria-live="polite"></div>`);
 const target=document.querySelector('#overview-results');
 function draw(){
  const terms=state.query.trim().toLocaleLowerCase('de').split(/\s+/).filter(Boolean);
  const matches=items.filter(item=>terms.every(term=>searchText(item).toLocaleLowerCase('de').includes(term)));
  const pages=Math.max(1,Math.ceil(matches.length/pageSize));
  state.page=Math.max(1,Math.min(state.page,pages));
  target.innerHTML=`<div class="list-meta"><strong>${matches.length} ${esc(countLabel)}</strong><span>${esc(listLabel)}</span></div>`+
   (matches.length?`<div class="table-wrap overview-table ${esc(tableClass)}"><table><colgroup>${columns.map(column=>`<col${column.className?` class="${esc(column.className)}"`:''}>`).join('')}</colgroup><thead><tr>${columns.map(column=>`<th>${esc(column.label)}</th>`).join('')}</tr></thead><tbody>${matches.slice((state.page-1)*pageSize,state.page*pageSize).map(renderRow).join('')}</tbody></table></div>`:
    `<div class="empty"><h2>${esc(terms.length?'Keine passenden Einträge gefunden.':emptyTitle)}</h2><p>${esc(terms.length?'Passe den Suchbegriff an.':emptyDescription)}</p></div>`)+
   `<div class="pagination"><button class="secondary" id="overview-prev" ${state.page===1?'disabled':''}>← Zurück</button><span>Seite ${state.page} / ${pages}</span><button class="secondary" id="overview-next" ${state.page===pages?'disabled':''}>Weiter →</button></div>`;
  bindRows(target);
  target.querySelector('#overview-prev').onclick=()=>{state.page--;draw();};
  target.querySelector('#overview-next').onclick=()=>{state.page++;draw();};
 }
 document.querySelector('#overview-search').onsubmit=event=>{
  event.preventDefault();state.query=new FormData(event.currentTarget).get('q');state.page=1;draw();
 };
 draw();
}
