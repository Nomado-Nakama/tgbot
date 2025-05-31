"""
Inline-keyboard helpers (pure functions, easy to unit-test).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.content_dao import Content

# ──────────────────────────────────────────
ROOT_BACK_ID = "back_root"


def build_children_kb(children: list[Content], *, parent_id: int | None) -> InlineKeyboardMarkup:
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
            text=child.title,
            callback_data=f"open_{child.id}",
        )

    kb.adjust(1)  # one column

    # nav buttons
    nav_row: list[InlineKeyboardButton] = [
        InlineKeyboardButton(text="🏠 Главная", callback_data=ROOT_BACK_ID)
    ]
    if parent_id is not None:
        nav_row.insert(
            0,
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_{parent_id}"),
        )
    kb.row(*nav_row)

    return kb.as_markup(resize_keyboard=True)
