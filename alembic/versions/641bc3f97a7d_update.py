"""Update

Revision ID: 641bc3f97a7d
Revises: a8b8b15abd8f
Create Date: 2025-07-09 16:18:51.918319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '641bc3f97a7d'
down_revision: Union[str, Sequence[str], None] = 'a8b8b15abd8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
