"""Allow user_id to be NULL in log table

Revision ID: f92871bcd939
Revises: d7f30cdb2e67
Create Date: 2025-08-23 22:53:15.696445

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f92871bcd939'
down_revision: Union[str, None] = 'd7f30cdb2e67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        ALTER TABLE public.bot_user_activity_log
        ALTER COLUMN user_id DROP NOT NULL;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        ALTER TABLE public.bot_user_activity_log
        ALTER COLUMN user_id SET NOT NULL;
    """)
