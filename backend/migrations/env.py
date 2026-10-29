from alembic import context
from backend.models import db
connection = context.config.attributes['connection']
context.configure(connection=connection, target_metadata=db.metadata, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
