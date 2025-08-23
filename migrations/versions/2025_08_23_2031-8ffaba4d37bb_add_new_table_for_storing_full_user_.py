"""add new table for storing full user activity log

Revision ID: 8ffaba4d37bb
Revises: 379ce429434e
Create Date: 2025-08-23 20:31:47.219577
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8ffaba4d37bb'
down_revision: Union[str, None] = '379ce429434e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        -- UUID generator for id
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        -- Полный лог активности пользователя Telegram-бота
        CREATE TABLE IF NOT EXISTS public.bot_user_activity_log (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            occurred_at       timestamptz NOT NULL DEFAULT now(), -- когда событие произошло/залогировалось
            user_id           bigint      NOT NULL,               -- Telegram user id
            chat_id           bigint,                              -- Telegram chat id (если применимо)
            message_id        bigint,                              -- message id (если применимо)
            update_id         bigint,                              -- update id из Telegram (если логируете)
            update_type       text        NOT NULL,                -- message|edited_message|callback_query|inline_query|...
            action            text,                                -- внутреннее имя хэндлера/действия
            command           text,                                -- текст команды (/start, /help, ...)
            state             text,                                -- текущее состояние FSM/машины состояний
            text              text,                                -- текст сообщения пользователя
            data              text,                                -- data из callback_query или иные строковые данные
            payload           jsonb       NOT NULL DEFAULT '{}'::jsonb, -- произвольный полезный JSON-пакет
            meta              jsonb       NOT NULL DEFAULT '{}'::jsonb, -- технические метаданные (latency, ip, user_agent...)
            is_error          boolean     NOT NULL DEFAULT false,  -- пометка, что событие об ошибке
            error_class       text,                                -- класс исключения (если is_error)
            error_message     text,                                -- сообщение ошибки (если is_error)
            error_traceback   text                                 -- traceback (если is_error)
        );

        COMMENT ON TABLE public.bot_user_activity_log IS
            'Full activity log of Telegram bot users (messages, callbacks, inline queries, handler actions, errors).';
        COMMENT ON COLUMN public.bot_user_activity_log.payload IS 'Arbitrary JSON payload captured with the event';
        COMMENT ON COLUMN public.bot_user_activity_log.meta    IS 'Technical metadata: timings, environment, etc.';

        -- Индексы для частых выборок
        CREATE INDEX IF NOT EXISTS bot_user_activity_log_user_at_idx
            ON public.bot_user_activity_log (user_id, occurred_at DESC);

        CREATE INDEX IF NOT EXISTS bot_user_activity_log_chat_at_idx
            ON public.bot_user_activity_log (chat_id, occurred_at DESC);

        CREATE INDEX IF NOT EXISTS bot_user_activity_log_is_error_at_idx
            ON public.bot_user_activity_log (is_error, occurred_at DESC);

        CREATE INDEX IF NOT EXISTS bot_user_activity_log_payload_gin_idx
            ON public.bot_user_activity_log USING gin (payload);

        CREATE INDEX IF NOT EXISTS bot_user_activity_log_meta_gin_idx
            ON public.bot_user_activity_log USING gin (meta);
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DROP TABLE IF EXISTS public.bot_user_activity_log;
        """
    )
