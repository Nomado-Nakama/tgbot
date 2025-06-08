"""add text_digest + embedded_at to content

Revision ID: 4103cc9ad149
Revises: 2df6976e3c09
Create Date: 2025-06-08 17:10:13.873150

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4103cc9ad149'
down_revision: Union[str, None] = '2df6976e3c09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
            ALTER TABLE content
                ADD COLUMN text_digest CHAR(64) NOT NULL DEFAULT '',
                ADD COLUMN embedded_at TIMESTAMPTZ;
            CREATE INDEX idx_content_text_digest ON content(text_digest);
        """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
            DROP INDEX IF EXISTS idx_content_text_digest;
            ALTER TABLE content
                DROP COLUMN embedded_at,
                DROP COLUMN text_digest;
        """)
