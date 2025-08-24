from __future__ import annotations

import re
from html import unescape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.content.models import Content

# ──────────────────────────────────────────
ROOT_BACK_ID = "back_root"

# pre-compiled once – cheap & fast
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_for_btn(text: str) -> str:
    """
    • Remove every HTML-tag/inline-formatting fragment
    • Convert entities (&nbsp;, &lt;, …) to real characters
    • Trim whitespace that breaks button rendering
    """
    return _TAG_RE.sub("", unescape(text)).strip()


def build_children_kb(
    children: list[Content],
    *,
    current_id: int | None = None,
    parent_id: int | None,
    main_menu=False,
    previous_menu_message_id = None,
) -> InlineKeyboardMarkup:
    """
    Build a keyboard:
      • One button per child (ordered)
      • "⬅️ Назад"  — only if *not* at root
      • "🏠 Главная" — always present
    """
    kb = InlineKeyboardBuilder()

    # children buttons
    for child in children:
        kb.button(
            text=_clean_for_btn(child.title),
            callback_data=f"open_{child.id}",
        )

    kb.adjust(1)  # one column

    # nav buttons
    if not main_menu:
        back_button_callback_data = f"back_{parent_id}" if parent_id else ROOT_BACK_ID

        kb.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_button_callback_data),
            InlineKeyboardButton(text="🏠 Главная", callback_data=ROOT_BACK_ID)
        )
        if current_id and previous_menu_message_id:
            save_button_callback_data = f"save_{current_id}_{previous_menu_message_id}"
            kb.row(
                InlineKeyboardButton(text="💾 Сохранить информацию в чате", callback_data=save_button_callback_data)
            )

    return kb.as_markup(resize_keyboard=True)
