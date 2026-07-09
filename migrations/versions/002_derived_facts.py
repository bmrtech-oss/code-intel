"""add derived facts table
Revision ID: 002
Revises: 001
Create Date: 2025-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('derived_facts',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('fact_type', sa.String, index=True),
        sa.Column('entity_id', sa.String, index=True, nullable=True),
        sa.Column('value', sa.Text),
        sa.Column('version', sa.String, index=True),
        sa.Column('depends_on', sa.ARRAY(sa.BigInteger)),
        sa.Column('depends_on_derived', sa.ARRAY(sa.BigInteger)),
        sa.Column('is_stale', sa.Boolean, default=False),
        sa.Column('last_validated', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )

def downgrade():
    op.drop_table('derived_facts')
