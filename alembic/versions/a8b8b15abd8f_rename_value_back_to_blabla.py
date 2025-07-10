"""Rename value back to blabla

Revision ID: a8b8b15abd8f
Revises: 359289ee28ff
Create Date: 2025-07-09 16:15:38.055216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8b8b15abd8f'
down_revision: Union[str, Sequence[str], None] = '359289ee28ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('test_items', 'value', new_column_name='blabla',
                    existing_type=sa.String(length=100),
                    nullable=False)

def downgrade():
    op.alter_column('test_items', 'blabla', new_column_name='value',
                    existing_type=sa.String(length=100),
                    nullable=False)
