"""create content table

Revision ID: 0e7a8abff60d
Revises:
Create Date: 2025-06-01 01:05:56.663788

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e7a8abff60d"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE content
            ALTER COLUMN title TYPE TEXT;
    """)


def downgrade() -> None:
    # -- shrink the column back to VARCHAR(100)
    op.execute("""
    ALTER TABLE content
        ALTER COLUMN title
        TYPE VARCHAR(100)
        USING LEFT(title, 100);
    """)
