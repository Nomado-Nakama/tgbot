import re
from html import escape

from loguru import logger
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.search_service import search_content
from src.bot.utils_html import is_balanced, escape

from src.bot.content_dao import get_children, get_content, get_breadcrumb
from src.bot.keyboard import ROOT_BACK_ID, build_children_kb, _clean_for_btn
from src.bot.utils_html import safe_html, split_html_safe, remove_seo_hashtags

router = Router(name="user")


WELCOME = """Привет!
Это <b>Nakama</b>, твой помощник в путешествиях 🌍✈️

Планируешь поездку, но не знаешь, с чего начать? Нужна ли виза в Японию, какая валюта в Грузии, когда лучше лететь в Турцию — ответы на эти и многие другие вопросы ты найдёшь в нашем боте.

Тебе остаётся лишь выбрать направление, а всё остальное мы берём на себя. <b>Готов начать?</b> -> /menu"""


def format_breadcrumb(items) -> str:
    from html import escape
    return " › ".join(escape(i.title, quote=False) for i in items)


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    await msg.answer(WELCOME)


@router.message(Command("menu"))
async def cmd_help(msg: Message) -> None:
    roots = await get_children(None)
    await msg.answer(
        "Меню:",
        reply_markup=build_children_kb(roots, parent_id=None),
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("open_"))
async def cb_open(cb: CallbackQuery) -> None:
    logger.debug(cb.data)
    item_id = int(cb.data.removeprefix("open_"))
    item = await get_content(item_id)
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb(item_id)
    breadcrumb = _clean_for_btn(format_breadcrumb(breadcrumb_items))

    children = await get_children(item.id)
    if children:  # category
        await cb.message.edit_text(
            f"📂 <b>{breadcrumb}</b>",
            reply_markup=build_children_kb(children, parent_id=item.parent_id),
            disable_web_page_preview=True
        )
    else:  # leaf
        # Split long text (TG limit 4096)
        logger.info(f"item: {item}")

        raw_body = item.body or "…"

        body_safe = safe_html(raw_body)
        logger.info(f"body_safe: {body_safe}")
        chunks = [remove_seo_hashtags(c).strip() for c in split_html_safe(body_safe, max_len=3800)]
        first_chunk = chunks[0]
        logger.info(f"chunks: {chunks}")
        # final defence – is it still balanced?
        if not is_balanced(first_chunk):
            logger.warning(
              f"Content {item.id} produced unbalanced HTML after hashtag removal "
              f"(len={len(first_chunk)})… sending plain-text fallback"
            )
            first_chunk = escape(re.sub(r"<[^>]+>", "", first_chunk))

        first_chunk = remove_seo_hashtags(first_chunk)
        logger.info(f"first_chunk: {first_chunk}")
        first_chunk = first_chunk.strip()
        logger.info(f"first_chunk.strip: {first_chunk}")
        complete_text = remove_seo_hashtags(f"<b>{breadcrumb}</b>\n\n{first_chunk}")
        logger.info(f"complete_text: {complete_text}")

        await cb.message.edit_text(
            complete_text,
            reply_markup=build_children_kb([], parent_id=item.parent_id),
            disable_web_page_preview=True
        )
        # optional follow-ups
        for chunk in chunks[1:]:
            await cb.message.answer(chunk)

    await cb.answer()  # remove loading state


@router.callback_query(F.data == ROOT_BACK_ID)
async def cb_home(cb: CallbackQuery) -> None:
    roots = await get_children(None)
    await cb.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=build_children_kb(roots, parent_id=None),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.callback_query(F.data.startswith("back_"))
async def cb_back(cb: CallbackQuery) -> None:
    parent_id = int(cb.data.removeprefix("back_"))
    siblings = await get_children(parent_id)
    parent_obj = await get_content(parent_id) if parent_id else None
    breadcrumb_items = await get_breadcrumb(parent_id)
    breadcrumb = _clean_for_btn(format_breadcrumb(breadcrumb_items))
    await cb.message.edit_text(
        f"📂 <b>{breadcrumb}</b>",
        reply_markup=build_children_kb(
            siblings,
            parent_id=parent_obj.parent_id if parent_obj else None,
        ),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.message()
async def msg_search(msg: Message) -> None:
    """
    Handle free-text user queries:
    1. Embed the query, search Qdrant, fetch the best match.
    2. Send a short teaser + button which opens the full article.
    Robust against empty/HTML-stripped articles (no IndexError).
    """
    query = msg.text or ""
    logger.info("msg_search: query=%r from user=%s", query, msg.from_user.id)

    no_results = True
    async for item, score in search_content(query, top_k=1):
        logger.debug("search hit: id=%s score=%s", item.id, score)

        breadcrumb_items = await get_breadcrumb(item.id)
        breadcrumb = _clean_for_btn(" › ".join(i.title for i in breadcrumb_items))

        raw_body = item.body or ""

        safe_body = safe_html(raw_body)
        chunks = [remove_seo_hashtags(c).strip() for c in split_html_safe(safe_body, max_len=3800)]

        if chunks:
            snippet_html = f"\n\n{chunks[0]}"
        else:
            logger.warning(f"Empty body for content id={item.id}")
            snippet_html = ""

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📖 Читать полностью", callback_data=f"open_{item.id}")]
            ]
        )

        await msg.answer(
            f"🔎 <b>{breadcrumb}</b>{snippet_html}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        no_results = False

    if no_results:
        await msg.answer("Ничего не найдено 😕")
