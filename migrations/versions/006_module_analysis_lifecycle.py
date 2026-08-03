"""add module analysis lifecycle tables
Revision ID: 006
Revises: 005
Create Date: 2025-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('module_analyses',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('module_path', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    op.create_index(op.f('ix_module_analyses_module_path'), 'module_analyses', ['module_path'], unique=False)

    op.create_table('analysis_versions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('module_analysis_id', sa.BigInteger(), nullable=False),
        sa.Column('git_commit_sha', sa.String(length=40), nullable=False),
        sa.Column('version_num', sa.Integer(), nullable=False),
        sa.Column('business_rules', sa.JSON(), nullable=True),
        sa.Column('edge_cases', sa.JSON(), nullable=True),
        sa.Column('data_transformations', sa.JSON(), nullable=True),
        sa.Column('side_effects', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    op.create_index(op.f('ix_analysis_versions_git_commit_sha'), 'analysis_versions', ['git_commit_sha'], unique=False)
    op.create_foreign_key(
        'fk_analysis_versions_module_analysis_id',
        'analysis_versions', 'module_analyses',
        ['module_analysis_id'], ['id'],
        ondelete='CASCADE'
    )

def downgrade():
    op.drop_constraint('fk_analysis_versions_module_analysis_id', 'analysis_versions', type_='foreignkey')
    op.drop_index(op.f('ix_analysis_versions_git_commit_sha'), table_name='analysis_versions')
    op.drop_table('analysis_versions')
    op.drop_index(op.f('ix_module_analyses_module_path'), table_name='module_analyses')
    op.drop_table('module_analyses')
