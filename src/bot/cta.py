from __future__ import annotations

from src.config import settings

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Callback identifiers (for analytics-friendly filtering in activity log)
CB_CTA_PROMPT = "cta_prompt"
CB_CTA_CHECK = "cta_check"
CB_CTA_SKIP = "cta_skip"


def build_soft_cta_kb(include_skip: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📰 Открыть канал", url=settings.CHANNEL_URL))
    kb.row(InlineKeyboardButton(text="✅ Я подписался", callback_data=CB_CTA_CHECK))
    if include_skip:
        kb.row(InlineKeyboardButton(text="⏭ Продолжить без подписки", callback_data=CB_CTA_SKIP))
    return kb.as_markup(resize_keyboard=True)
