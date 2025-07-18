"""create kv table for google-doc revision tracking

Revision ID: 379ce429434e
Revises: 4103cc9ad149
Create Date: 2025-06-08 17:11:26.242276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '379ce429434e'
down_revision: Union[str, None] = '2df6976e3c09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE kv (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO kv(key, value) VALUES ('doc_revision', '');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE kv;")
