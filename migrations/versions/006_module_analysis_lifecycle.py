"""add module analysis lifecycle tables and timeline columns
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
    # Create module_analyses
    op.create_table('module_analyses',
        sa.Column('id', sa.BigInteger, autoincrement=True, primary_key=True),
        sa.Column('module_path', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    op.create_index(op.f('ix_module_analyses_module_path'), 'module_analyses', ['module_path'], unique=False)

    # Create analysis_versions
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

    # Add historical timeline columns to graph_nodes
    op.add_column('graph_nodes', sa.Column('valid_from_sha', sa.String(), nullable=True))
    op.add_column('graph_nodes', sa.Column('valid_to_sha', sa.String(), nullable=True))
    op.create_index(op.f('ix_graph_nodes_valid_from_sha'), 'graph_nodes', ['valid_from_sha'], unique=False)
    op.create_index(op.f('ix_graph_nodes_valid_to_sha'), 'graph_nodes', ['valid_to_sha'], unique=False)

    # Add historical timeline columns to graph_edges
    op.add_column('graph_edges', sa.Column('valid_from_sha', sa.String(), nullable=True))
    op.add_column('graph_edges', sa.Column('valid_to_sha', sa.String(), nullable=True))
    op.create_index(op.f('ix_graph_edges_valid_from_sha'), 'graph_edges', ['valid_from_sha'], unique=False)
    op.create_index(op.f('ix_graph_edges_valid_to_sha'), 'graph_edges', ['valid_to_sha'], unique=False)

def downgrade():
    # Drop historical timeline columns from graph_edges
    op.drop_index(op.f('ix_graph_edges_valid_to_sha'), table_name='graph_edges')
    op.drop_index(op.f('ix_graph_edges_valid_from_sha'), table_name='graph_edges')
    op.drop_column('graph_edges', 'valid_to_sha')
    op.drop_column('graph_edges', 'valid_from_sha')

    # Drop historical timeline columns from graph_nodes
    op.drop_index(op.f('ix_graph_nodes_valid_to_sha'), table_name='graph_nodes')
    op.drop_index(op.f('ix_graph_nodes_valid_from_sha'), table_name='graph_nodes')
    op.drop_column('graph_nodes', 'valid_to_sha')
    op.drop_column('graph_nodes', 'valid_from_sha')

    # Drop module_analyses and analysis_versions tables
    op.drop_constraint('fk_analysis_versions_module_analysis_id', 'analysis_versions', type_='foreignkey')
    op.drop_index(op.f('ix_analysis_versions_git_commit_sha'), table_name='analysis_versions')
    op.drop_table('analysis_versions')
    op.drop_index(op.f('ix_module_analyses_module_path'), table_name='module_analyses')
    op.drop_table('module_analyses')
