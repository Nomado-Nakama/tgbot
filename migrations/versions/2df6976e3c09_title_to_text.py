"""title to text

Revision ID: 2df6976e3c09
Revises: 0e7a8abff60d
Create Date: 2025-06-03 21:57:25.862393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2df6976e3c09'
down_revision: Union[str, None] = '0e7a8abff60d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
