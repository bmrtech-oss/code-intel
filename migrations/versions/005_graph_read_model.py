"""add graph read model
Revision ID: 005
Revises: 004
Create Date: 2025-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('graph_nodes',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('fqn', sa.String, index=True),
        sa.Column('kind', sa.String),
        sa.Column('file', sa.String),
        sa.Column('version', sa.String, index=True),
        sa.Column('introduced_in', sa.String),
        sa.Column('deleted_in', sa.String, nullable=True)
    )
    
    op.create_table('graph_edges',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('from_fqn', sa.String, index=True),
        sa.Column('to_fqn', sa.String, index=True),
        sa.Column('edge_type', sa.String, index=True),
        sa.Column('version', sa.String, index=True),
        sa.Column('confidence', sa.Float),
        sa.Column('introduced_in', sa.String),
        sa.Column('deleted_in', sa.String, nullable=True)
    )

def downgrade():
    op.drop_table('graph_edges')
    op.drop_table('graph_nodes')
