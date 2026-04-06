"""initial schema
Revision ID: 001
Revises: 
Create Date: 2025-04-05
"""
from alembic import op
import sqlalchemy as sa
import pgvector
revision = '001'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('facts',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('entity_type', sa.String),
        sa.Column('entity_id', sa.String),
        sa.Column('attribute', sa.String),
        sa.Column('value', sa.Text),
        sa.Column('version', sa.String),
        sa.Column('valid_from', sa.DateTime),
        sa.Column('valid_to', sa.DateTime, nullable=True),
        sa.Column('embedding', pgvector.VECTOR(384), nullable=True)
    )
    op.create_index('idx_facts_version', 'facts', ['version'])
    op.create_index('idx_facts_entity', 'facts', ['entity_type', 'entity_id'])
    op.execute("CREATE VIEW current_symbols AS SELECT DISTINCT entity_id as symbol_id, attribute as name, value as kind, version FROM facts WHERE entity_type='symbol' AND valid_to IS NULL")
    op.execute("CREATE VIEW current_calls AS SELECT entity_id as caller, value as callee, version FROM facts WHERE entity_type='call' AND attribute='callee' AND valid_to IS NULL")
def downgrade():
    op.drop_view('current_calls')
    op.drop_view('current_symbols')
    op.drop_table('facts')
    op.execute("DROP EXTENSION IF EXISTS vector")
