"""add_users_chats_and_deliveries

Revision ID: d7f30cdb2e67
Revises: 8ffaba4d37bb
Create Date: 2025-08-23 21:56:17.568543

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd7f30cdb2e67'
down_revision: Union[str, None] = '8ffaba4d37bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.tg_users (
        user_id      bigint PRIMARY KEY,
        is_bot       boolean NOT NULL DEFAULT false,
        first_name   text,
        last_name    text,
        username     text,
        language_code text,
        is_premium   boolean,
        added_at     timestamptz NOT NULL DEFAULT now(),
        updated_at   timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS public.tg_chats (
        chat_id      bigint PRIMARY KEY,
        type         text NOT NULL,               -- private, group, supergroup, channel
        title        text,
        username     text,
        first_name   text,
        last_name    text,
        added_at     timestamptz NOT NULL DEFAULT now(),
        updated_at   timestamptz NOT NULL DEFAULT now()
    );

    -- What exactly we sent after a user action
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS public.bot_user_deliveries (
        id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        occurred_at       timestamptz NOT NULL DEFAULT now(),
        activity_id       uuid NOT NULL
            REFERENCES public.bot_user_activity_log(id) ON DELETE CASCADE,
        user_id           bigint NOT NULL,
        chat_id           bigint NOT NULL,
        message_id        bigint NOT NULL,
        method            text   NOT NULL,                -- sendMessage, editMessageText, sendPhoto, etc.
        sent_text         text,                           -- text or caption that user actually sees
        text_digest       bpchar(64),                     -- snapshot digest for joins/grouping
        content_title     text,                           -- optional snapshot from `content` table
        content_body      text,                           -- optional snapshot (cleaned/trimmed if needed)
        breadcrumb        text,                           -- optional snapshot of breadcrumb shown to user
        payload           jsonb NOT NULL DEFAULT '{}'::jsonb
    );

    CREATE INDEX IF NOT EXISTS bot_user_deliveries_activity_idx
        ON public.bot_user_deliveries (activity_id);

    CREATE INDEX IF NOT EXISTS bot_user_deliveries_user_at_idx
        ON public.bot_user_deliveries (user_id, occurred_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS public.bot_user_deliveries;
    DROP TABLE IF EXISTS public.tg_chats;
    DROP TABLE IF EXISTS public.tg_users;
    """)
