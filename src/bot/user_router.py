from loguru import logger
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.search_service import search_content

from src.bot.content_dao import get_children, get_content, get_breadcrumb
from src.bot.keyboard import ROOT_BACK_ID, build_children_kb


router = Router(name="user")


WELCOME = (
    "👋 Привет!\n"
    "Используй кнопки ниже, чтобы найти нужную информацию.\n"
    "Команда /menu покажет выбор стран."
    "Напиши интересующий тебя вопрос текстом, "
    "а мы попробуем найти наиболее подходящий ответ."
)


def format_breadcrumb(items) -> str:
    return " › ".join(i.title for i in items)


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    await msg.answer(WELCOME)


@router.message(Command("menu"))
async def cmd_help(msg: Message) -> None:
    roots = await get_children(None)
    await msg.answer("Меню:", reply_markup=build_children_kb(roots, parent_id=None))


@router.callback_query(F.data.startswith("open_"))
async def cb_open(cb: CallbackQuery) -> None:
    item_id = int(cb.data.removeprefix("open_"))
    item = await get_content(item_id)
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb(item_id)
    breadcrumb = format_breadcrumb(breadcrumb_items)

    children = await get_children(item.id)
    if children:  # category
        await cb.message.edit_text(
            f"📂 <b>{breadcrumb}</b>",
            reply_markup=build_children_kb(children, parent_id=item.parent_id),
        )
    else:  # leaf
        # Split long text (TG limit 4096)
        body = item.body or "…"
        chunks = [body[i: i + 4000] for i in range(0, len(body), 4000)]
        await cb.message.edit_text(
            f"<b>{breadcrumb}</b>\n\n{chunks[0]}",
            reply_markup=build_children_kb([], parent_id=item.parent_id),
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
    )
    await cb.answer()


@router.callback_query(F.data.startswith("back_"))
async def cb_back(cb: CallbackQuery) -> None:
    parent_id = int(cb.data.removeprefix("back_"))
    siblings = await get_children(parent_id)
    parent_obj = await get_content(parent_id) if parent_id else None
    title = parent_obj.title if parent_obj else "Главное меню"
    await cb.message.edit_text(
        f"📂 <b>{title}</b>",
        reply_markup=build_children_kb(
            siblings,
            parent_id=parent_obj.parent_id if parent_obj else None,
        ),
    )
    await cb.answer()


@router.message()
async def msg_search(msg: Message):
    logger.info(f"Got msg: {msg.text} from {msg.from_user.username}...")
    search_results = search_content(msg.text, top_k=1)
    async for item, score in search_results:
        breadcrumb_items = await get_breadcrumb(item.id)
        breadcrumb = format_breadcrumb(breadcrumb_items)

        logger.info(f"Found item: {item} score: {score}...")
        snippet = (item.body or "")[:400] + ("…" if item.body and len(item.body) > 400 else "")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📖 Читать полностью", callback_data=f"open_{item.id}")]
            ]
        )
        await msg.answer(
            f"🔎 <b>{breadcrumb}</b>\n\n{snippet}",
            reply_markup=kb,
        )

    if not search_results:
        await msg.answer("Ничего не найдено 😕")
