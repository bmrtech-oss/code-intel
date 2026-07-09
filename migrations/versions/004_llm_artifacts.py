"""add llm artifacts table
Revision ID: 004
Revises: 003
Create Date: 2025-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('llm_artifacts',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('artifact_type', sa.String, index=True),
        sa.Column('entity_id', sa.String, index=True, nullable=True),
        sa.Column('value', sa.Text),
        sa.Column('version', sa.String, index=True),
        sa.Column('grounded_in', sa.ARRAY(sa.BigInteger)),
        sa.Column('generation_prompt', sa.Text),
        sa.Column('model_version', sa.String),
        sa.Column('is_verified', sa.Boolean, default=True),
        sa.Column('confidence', sa.Float, default=1.0),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('llm_artifacts')
