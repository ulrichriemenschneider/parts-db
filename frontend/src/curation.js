export function curationBadges(curation={}) {
 const reichelt=curation.reichelt_at!=null;
 const manual=curation.manual_status;
 return `<span class="curation-badges">${reichelt?'<span class="curation-mark reichelt" role="img" aria-label="Mit Reichelt-Daten ergänzt" title="Mit Reichelt-Daten ergänzt">R</span>':''}${manual==='partial'?'<span class="curation-mark manual-partial" role="img" aria-label="Teilweise manuell gepflegt" title="Teilweise manuell gepflegt">✓</span>':manual==='complete'?'<span class="curation-mark manual-complete" role="img" aria-label="Vollständig manuell geprüft" title="Vollständig manuell geprüft">✓</span>':''}</span>`;
}
