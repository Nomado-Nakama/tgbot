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
    op.execute(
        """
        CREATE TABLE content (
            id         BIGSERIAL PRIMARY KEY,
            parent_id  BIGINT REFERENCES content(id) ON DELETE CASCADE,
            title      VARCHAR(100) NOT NULL,
            body       TEXT,
            ord        INTEGER      DEFAULT 0,
            created_at TIMESTAMPTZ  DEFAULT now()
        );
        CREATE INDEX idx_content_parent ON content(parent_id);
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content CASCADE;")
