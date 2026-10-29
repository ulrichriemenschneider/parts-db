from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)

class Session(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    csrf = db.Column(db.String(64), nullable=False)
    expires = db.Column(db.Float, nullable=False)
    import_digest = db.Column(db.String(64))
    import_state = db.Column(db.String(64))
    demand_preview = db.Column(db.JSON)
    enrichment_preview = db.Column(db.JSON)
    reichelt_preview = db.Column(db.JSON)
    reset_preview = db.Column(db.JSON)

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(100), nullable=False, index=True)
    at = db.Column(db.Float, nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    fields = db.Column(db.JSON, nullable=False, default=list)


class CategoryNode(db.Model):
    """Supplier hierarchy separate from the stable categories.csv columns."""
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='CASCADE'), primary_key=True)
    reichelt_id = db.Column(db.Integer, nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    label = db.Column(db.String(300), nullable=False)
    source_url = db.Column(db.Text, nullable=False)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('location.id'))

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    manufacturer = db.Column(db.String(200), nullable=False, default='')
    mpn = db.Column(db.String(200), nullable=False, default='')
    package = db.Column(db.String(200), nullable=False, default='')
    description = db.Column(db.Text, nullable=False, default='')
    notes = db.Column(db.Text, nullable=False, default='')
    attributes = db.Column(db.JSON, nullable=False, default=dict)

class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('part.id', ondelete='CASCADE'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    article_number = db.Column(db.String(200), nullable=False, default='')
    product_url = db.Column(db.Text, nullable=False, default='')
    datasheet_url = db.Column(db.Text, nullable=False, default='')

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('part.id', ondelete='CASCADE'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('part_id', 'location_id'), CheckConstraint('quantity >= 0'))


class DemandList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_filename = db.Column(db.String(255), nullable=False)
    source_digest = db.Column(db.String(64), nullable=False)
    imported_at = db.Column(db.Float, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint('version >= 1'), {'sqlite_autoincrement': True})


class DemandItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('demand_list.id', ondelete='CASCADE'), nullable=False, index=True)
    part_id = db.Column(db.Integer, db.ForeignKey('part.id'), nullable=False)
    article_number = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    received = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.Text, nullable=False, default='')
    __table_args__ = (UniqueConstraint('list_id', 'article_number'),
                     CheckConstraint('quantity > 0'), CheckConstraint('received >= 0 AND received <= quantity'),
                     {'sqlite_autoincrement': True})


class GoodsReceipt(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('demand_list.id', ondelete='CASCADE'), nullable=False)
    payload_digest = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.Float, nullable=False)
    items = db.Column(db.JSON, nullable=False)


class ProductCache(db.Model):
    article_number = db.Column(db.String(200), primary_key=True)
    fetched_at = db.Column(db.Float, nullable=False)
    data = db.Column(db.JSON, nullable=False)


class ProductFetchState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lease = db.Column(db.String(64), nullable=False, default='')
    lease_until = db.Column(db.Float, nullable=False, default=0)
    last_started = db.Column(db.Float, nullable=False, default=0)
    blocked_until = db.Column(db.Float, nullable=False, default=0)


class PartCuration(db.Model):
    part_id = db.Column(db.Integer, db.ForeignKey('part.id', ondelete='CASCADE'), primary_key=True)
    reichelt_at = db.Column(db.Float)
    manual_status = db.Column(db.String(12), nullable=False, default='none')
    __table_args__ = (CheckConstraint("manual_status IN ('none', 'partial', 'complete')"),)
