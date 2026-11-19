"""Add local chart configuration storage only.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chart_workspaces',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(140), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('configuration', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('configuration_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('chart_workspaces')

