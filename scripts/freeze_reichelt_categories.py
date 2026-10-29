"""Validate a completed public crawl and freeze its category snapshot."""
import argparse
from collections import Counter
import json
from pathlib import Path


def freeze(state):
    if not state.get('completed_at') or state.get('last_error') or state['queue']:
        raise ValueError('Nur ein vollständig abgeschlossener Abruf kann übernommen werden.')
    nodes = {int(key):value for key,value in state['nodes'].items()}
    if not nodes or any(node.get('branch') and not node.get('checked') for node in nodes.values()):
        raise ValueError('Ungeprüfte Untergruppen vorhanden.')
    def path(ident, seen=()):
        if ident in seen or ident not in nodes:
            raise ValueError('Kreis oder fehlender Elternknoten im Kategorienbaum.')
        node = nodes[ident]
        return (path(node['parent_id'],(*seen,ident))+' › ' if node.get('parent_id') else '')+node['name']
    paths = {ident:path(ident) for ident in nodes}
    counts = Counter(paths.values())
    rows = [dict(id=ident,name=node['name'],parent_id=node.get('parent_id'),url=node['url'],
                 path=paths[ident]+(f' [Reichelt {ident}]' if counts[paths[ident]] > 1 else ''))
            for ident,node in sorted(nodes.items())]
    sitemap_ids = sorted({int(url.rsplit('-',1)[1]) for url in state['sitemap_urls']})
    if any(ident not in nodes for ident in sitemap_ids):
        raise ValueError('Einträge aus den offiziellen Sitemaps fehlen.')
    if any(not row['name'] or len(row['path']) > 200 for row in rows):
        raise ValueError('Leerer oder zu langer Kategorienpfad.')
    return dict(retrieved_at=state['completed_at'],source='https://www.reichelt.de/de/de/',
                sitemap_index='https://www.reichelt.de/sitemap.xml',sitemaps=state['sitemaps'],
                main_groups=state['sources'],category_count=len(rows),sitemap_category_count=len(sitemap_ids),
                sitemap_category_ids=sitemap_ids,checked_group_pages=len(state['visited']),
                checked_group_urls=state['visited'],unresolved_urls=[],categories=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint',type=Path)
    parser.add_argument('destination',type=Path)
    args = parser.parse_args()
    snapshot = freeze(json.loads(args.checkpoint.read_text()))
    args.destination.parent.mkdir(parents=True,exist_ok=True)
    args.destination.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    print(f"{snapshot['category_count']} Kategorien validiert; {snapshot['sitemap_category_count']} Sitemap-Kategorien vollständig enthalten.")
