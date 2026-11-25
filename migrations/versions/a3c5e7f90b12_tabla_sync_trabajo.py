"""tabla sync_trabajo

Revision ID: a3c5e7f90b12
Revises: 37ad69d39f73
Create Date: 2026-11-20 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c5e7f90b12'
down_revision: Union[str, Sequence[str], None] = '37ad69d39f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('sync_trabajo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(), nullable=False),
    sa.Column('origen', sa.String(), nullable=False),
    sa.Column('inicio', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tipos', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('sync_trabajo')
