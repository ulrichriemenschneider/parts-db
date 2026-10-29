"""Reichelt category identity, hierarchy and product breadcrumb resolution."""
from sqlalchemy import select

from .models import db, Category, CategoryNode


LEGACY_IDS = {'Widerstände':3059, 'Kondensatoren':3140, 'Dioden':2985,
              'Transistoren':2878, 'ICs':2906, 'Module / Arduino':8241, 'Sonstiges':2875}


def category_data(category, nodes=None):
    node = nodes.get(category.id) if nodes is not None else db.session.get(CategoryNode, category.id)
    return dict(id=category.id, name=category.name, fields=category.fields,
                label=node.label if node else category.name, parent_id=node.parent_id if node else None,
                reichelt_id=node.reichelt_id if node else None, source_url=node.source_url if node else '',
                path=category.name)


def by_reichelt_id(ident):
    return db.session.scalar(select(Category).join(CategoryNode, CategoryNode.category_id == Category.id)
                             .where(CategoryNode.reichelt_id == ident))


def default_category():
    return by_reichelt_id(2875)


def resolve_category(suggestion, fallback=None):
    for ident in reversed(suggestion.get('category_ids', [])):
        if isinstance(ident, int) and (category := by_reichelt_id(ident)):
            return category
    names = [name.strip() for name in suggestion.get('category_path', [])
             if isinstance(name, str) and name.strip() and name.strip() not in ('Startseite', 'Home')]
    if names:
        # Breadcrumb labels are canonical and disambiguate identically named leaves.
        # The supplier sometimes removes an old top-level breadcrumb. A complete
        # canonical suffix still identifies the same category unambiguously.
        for start in range(len(names)):
            path = ' › '.join(names[start:])
            category = db.session.scalar(select(Category).where(Category.name == path))
            if category:
                return category
        if len(names) == 1:
            matches = db.session.scalars(select(Category).join(CategoryNode, CategoryNode.category_id == Category.id)
                                         .where(CategoryNode.label == names[0])).all()
            if len(matches) == 1:
                return matches[0]
    family = suggestion.get('category_name', 'Sonstiges')
    if family == 'Sonstiges' and fallback:
        return fallback
    return by_reichelt_id(LEGACY_IDS.get(family, 2875)) or fallback or default_category()


def descendants(ident):
    children = {}
    for node in db.session.scalars(select(CategoryNode)):
        children.setdefault(node.parent_id, []).append(node.category_id)
    found, pending = set(), [ident]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(children.get(current, []))
    return found
