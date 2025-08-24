from loguru import logger
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from src.bot.content_dao import get_children, get_content, get_breadcrumb
from src.bot.keyboard import ROOT_BACK_ID, build_children_kb, _clean_for_btn
from src.bot.renderers.content_renderer import build_breadcrumb_text, render_leaf_message

router = Router(name="user")

WELCOME = """Привет!

Добро пожаловать в уникального помощника для твоих путешествий! 🌍✈️

Внутри бота ты найдёшь самую важную и полезную информацию по каждой стране: от оформления визы и особенностей транспорта до местной кухни и полезных советов, основанных на нашем личном опыте!

Тебе остаётся лишь выбрать направление, а всё остальное мы берём на себя. <b>Готов начать?</b> -> /menu"""


# А еще наш бот умеет отвечать на твои открытые вопросы – просто задай свой вопрос, и бот подберёт для тебя наиболее подходящий ответ из нашей базы знаний.


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    await msg.answer(WELCOME)


@router.message(Command("menu"))
async def cmd_help(msg: Message) -> None:
    roots = await get_children(None)
    await msg.answer(
        "Выбирай страну, о которой хочешь узнать полезную информацию:",
        reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("open_"))
async def cb_open(cb: CallbackQuery) -> None:
    item_id = int(cb.data.removeprefix("open_"))
    item = await get_content(item_id)
    logger.info(f"Got {item}, parent_id = {getattr(item, 'parent_id', None)}")
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb(item_id)
    breadcrumb = _clean_for_btn(build_breadcrumb_text(breadcrumb_items))

    children = await get_children(item.id)
    if children:  # category
        logger.info(f"item: {item}")
        await cb.message.edit_text(
            f"📂 <b>{breadcrumb}</b>",
            reply_markup=build_children_kb(children, parent_id=item.parent_id),
            disable_web_page_preview=True
        )
        await cb.answer()
        return

    # Split long text (TG limit 4096)
    logger.info(f"item: {item}")
    logger.info(f"message: {cb.message.message_id}")

    complete_text, extra_chunks = render_leaf_message(item, breadcrumb_items)

    await cb.message.edit_text(
        complete_text,
        reply_markup=build_children_kb(
            [],
            parent_id=item.parent_id,  # keep real parent_id; root handled inside keyboard
            current_id=item.id,
            previous_menu_message_id=cb.message.message_id,
        ),
        disable_web_page_preview=True,
    )
    for chunk in extra_chunks:
        await cb.message.answer(chunk)

    await cb.answer()  # remove loading state


@router.callback_query(F.data == ROOT_BACK_ID)
async def cb_home(cb: CallbackQuery) -> None:
    roots = await get_children(None)
    await cb.message.edit_text(
        "Выбирай страну, о которой хочешь узнать полезную информацию:",
        reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.callback_query(F.data.startswith("back_"))
async def cb_back(cb: CallbackQuery) -> None:
    parent_id = int(cb.data.removeprefix("back_"))
    siblings = await get_children(parent_id)
    parent_obj = await get_content(parent_id) if parent_id else None
    breadcrumb_items = await get_breadcrumb(parent_id)
    breadcrumb = _clean_for_btn(build_breadcrumb_text(breadcrumb_items))
    await cb.message.edit_text(
        f"📂 <b>{breadcrumb}</b>",
        reply_markup=build_children_kb(
            siblings,
            parent_id=parent_obj.parent_id if parent_obj else None,
        ),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.callback_query(F.data.startswith("save_"))
async def cb_save(cb: CallbackQuery) -> None:
    item_id = int(cb.data.removeprefix("save_").split('_')[0])
    prev_menu_message_id = int(cb.data.removeprefix("save_").split('_')[1])
    item = await get_content(item_id)
    logger.info(f"Got {item}, parent_id = {getattr(item, 'parent_id', None)}")
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb(item_id)
    complete_text, extra_chunks = render_leaf_message(item, breadcrumb_items)

    # 1) Post a copy “as is” (the original “save into chat” behavior)
    await cb.message.answer(
        complete_text,
        disable_web_page_preview=True
    )
    for chunk in extra_chunks:
        await cb.message.answer(chunk)

    # 2) Delete previous menu and re-post content with keyboard
    await cb.bot.delete_message(chat_id=cb.message.chat.id, message_id=prev_menu_message_id)
    await cb.message.answer(
        text=complete_text,
        reply_markup=build_children_kb(
            [],
            parent_id=item.parent_id,
            current_id=item.id,
            previous_menu_message_id=cb.message.message_id
        ),
        disable_web_page_preview=True
    )

# @router.message()
# async def msg_search(msg: Message) -> None:
#     """
#     Handle free-text user queries:
#     1. Embed the query, search Qdrant, fetch the best match.
#     2. Send a short teaser + button which opens the full article.
#     Robust against empty/HTML-stripped articles (no IndexError).
#     """
#     query = msg.text or ""
#     logger.info("msg_search: query=%r from user=%s", query, msg.from_user.id)
#
#     no_results = True
#     async for item, score in search_content(query, top_k=1):
#         logger.debug("search hit: id=%s score=%s", item.id, score)
#
#         breadcrumb_items = await get_breadcrumb(item.id)
#         breadcrumb = _clean_for_btn(" › ".join(i.title for i in breadcrumb_items))
#
#         raw_body = item.body or ""
#
#         safe_body = safe_html(raw_body)
#         chunks = [remove_seo_hashtags(c).strip() for c in split_html_safe(safe_body, max_len=3800)]
#
#         if chunks:
#             snippet_html = f"\n\n{chunks[0]}"
#         else:
#             logger.warning(f"Empty body for content id={item.id}")
#             snippet_html = ""
#
#         kb = InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [InlineKeyboardButton(text="📖 Читать полностью", callback_data=f"open_{item.id}")]
#             ]
#         )
#
#         await msg.answer(
#             f"🔎 <b>{breadcrumb}</b>{snippet_html}",
#             reply_markup=kb,
#             disable_web_page_preview=True,
#         )
#         no_results = False
#
#     if no_results:
#         await msg.answer("Ничего не найдено 😕")
