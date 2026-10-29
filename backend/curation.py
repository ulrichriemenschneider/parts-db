"""Curation metadata stays separate from the stable inventory CSV schema."""
import time
from .models import db, PartCuration


def part_data(part):
    metadata = db.session.get(PartCuration, part.id)
    return {**{column.name:getattr(part,column.name) for column in part.__table__.columns},
            'curation': {'reichelt_at':metadata.reichelt_at if metadata else None,
                         'manual_status':metadata.manual_status if metadata else 'none'}}


def metadata_for(part):
    db.session.flush()
    metadata = db.session.get(PartCuration, part.id)
    if metadata is None:
        metadata = PartCuration(part_id=part.id, manual_status='none')
        db.session.add(metadata)
    return metadata


def manual_status(data):
    status = data.pop('manual_status', None)
    if status is not None and status not in ('none','partial','complete'):
        raise ValueError('Manueller Pflegestand muss none, partial oder complete sein.')
    return status


def mark_manual(part, status=None):
    metadata_for(part).manual_status = status if status is not None else 'partial'


def mark_reichelt(part, fetched_at=None):
    metadata_for(part).reichelt_at = fetched_at if fetched_at is not None else time.time()
