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
            id bigserial NOT NULL,
            parent_id int8 NULL,
            title text NOT NULL,
            body text NULL,
            ord int4 DEFAULT 0 NULL,
            created_at timestamptz DEFAULT now() NULL,
            text_digest bpchar(64) DEFAULT ''::bpchar NOT NULL,
            embedded_at timestamptz NULL,
            CONSTRAINT content_pkey PRIMARY KEY (id),
            CONSTRAINT content_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public."content"(id) ON DELETE CASCADE
        );
        
        CREATE INDEX idx_content_text_digest ON public.content USING btree (text_digest);
        """
    )


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS idx_content_text_digest;
        DROP TABLE IF EXISTS content;
    """)
