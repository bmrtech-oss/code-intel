"""add extractor versioning
Revision ID: 003
Revises: 002
Create Date: 2025-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('facts', sa.Column('extractor_version', sa.String, nullable=True))
    op.create_index('idx_facts_extractor_version', 'facts', ['extractor_version'])
    
    op.add_column('derived_facts', sa.Column('extractor_version', sa.String, nullable=True))
    op.create_index('idx_derived_facts_extractor_version', 'derived_facts', ['extractor_version'])
    
    op.create_table('version_metadata',
        sa.Column('key', sa.String, primary_key=True),
        sa.Column('value', sa.String)
    )

def downgrade():
    op.drop_table('version_metadata')
    op.drop_column('derived_facts', 'extractor_version')
    op.drop_column('facts', 'extractor_version')
