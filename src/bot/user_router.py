from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from src.bot.keyboard import ROOT_BACK_ID, build_children_kb
from src.bot.cache_layer import (
    get_children_cached,
    get_content_cached,
    get_breadcrumb_cached,
    build_breadcrumb_text_cached,
    render_leaf_message_cached,
    _clean_for_btn_cached,
)

from src.bot.cta import (
    CB_CTA_PROMPT, CB_CTA_CHECK, CB_CTA_SKIP,
    build_soft_cta_kb
)

import time
from typing import Dict, Tuple

from loguru import logger
from aiogram.enums import ChatMemberStatus
from src.config import settings

router = Router(name="user")
CTA_MESSAGE = f"""А еще мы публикуем новые лайфхаки и апдейты по боту в нашем тг канале! -> {settings.CHANNEL_URL}
Подпишись, чтобы получать самое полезное без спама 😊"""

WELCOME_BASE = """Привет!

Добро пожаловать в уникального помощника для твоих путешествий! 🌍✈️

Внутри бота ты найдёшь самую важную и полезную информацию по каждой стране: от оформления визы и особенностей транспорта до местной кухни и полезных советов, основанных на нашем личном опыте!

Тебе остаётся лишь выбрать направление, а всё остальное мы берём на себя. <b>Готов начать?</b> -> /menu
"""

WELCOME_WITH_CTA = f"""{WELCOME_BASE}

{CTA_MESSAGE}
"""

# А еще наш бот умеет отвечать на твои открытые вопросы – просто задай свой вопрос, и бот подберёт для тебя наиболее подходящий ответ из нашей базы знаний.

async def _show_soft_cta(message: Message, custom_cta_message: str = None) -> None:
    if not custom_cta_message:
        custom_cta_message = WELCOME_WITH_CTA
    ok = await _is_user_subscribed(message.bot, message.from_user.id)
    logger.info(f"User: {message.from_user}, is subscribed? - {ok}")
    if not ok:
        await message.answer(
            custom_cta_message,
            reply_markup=build_soft_cta_kb(include_skip=True),
            disable_web_page_preview=True,
        )


async def _is_user_subscribed(bot, user_id: int) -> bool:
    """
    Проверка подписки через getChatMember с кэшированием только положительных результатов.
    - Кэшируем ТОЛЬКО статусы подписки (creator/administrator/member) на ограниченное время (TTL).
    - Ошибки API и 'не подписан' не кэшируем (чтобы быстро отловить новую подписку).
    """
    # Ленивая инициализация кэша на атрибутах функции, чтобы не трогать внешний модульный скоуп.
    if not hasattr(_is_user_subscribed, "_cache"):
        # key: (channel_id_or_username, user_id) -> expires_at_monotonic
        _is_user_subscribed._cache: Dict[Tuple[str | int, int], float] = {}
        # Разумный TTL, чтобы не держать "вечную" подписку, если пользователь отписался.
        _is_user_subscribed._ttl_seconds: float = 6 * 60 * 60  # 6 часов

    cache: Dict[Tuple[str | int, int], float] = _is_user_subscribed._cache  # type: ignore[attr-defined]
    ttl: float = _is_user_subscribed._ttl_seconds  # type: ignore[attr-defined]
    now = time.monotonic()

    channel_key: Tuple[str | int, int] = (settings.CHANNEL_ID_OR_USERNAME, user_id)

    # 1) Быстрый путь: есть валидный "подписан" в кэше.
    expires_at = cache.get(channel_key)
    if expires_at is not None:
        if expires_at > now:
            return True  # кэшированный "подписан"
        # просрочен — убираем
        cache.pop(channel_key, None)

    # 2) Живой вызов API: только он дает актуальный статус.
    try:
        m = await bot.get_chat_member(
            chat_id=settings.CHANNEL_ID_OR_USERNAME,
            user_id=user_id,
        )
    except Exception as e:
        logger.exception(e)
        # Возможные причины: бот не админ канала / канал приватный / пользователь не виден боту.
        # Ничего не кэшируем — считаем "не подписан".
        return False

    status = getattr(m, "status", None)
    is_subscribed = status in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    }

    # 3) Кэшируем ТОЛЬКО положительный результат.
    if is_subscribed:
        cache[channel_key] = now + ttl
    else:
        # Гарантированно не храним отрицательные статусы.
        cache.pop(channel_key, None)

    return is_subscribed


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    if not await _is_user_subscribed(msg.bot, msg.from_user.id):
        await _show_soft_cta(msg)
    else:
        await msg.answer(WELCOME_BASE)


@router.message(Command("menu"))
async def cmd_help(msg: Message) -> None:
    roots = await get_children_cached(None)
    await msg.answer(
        "Выбирай страну, о которой хочешь узнать полезную информацию:",
        reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
        disable_web_page_preview=True
    )
    # Покажем мягкий CTA как второе сообщение (всегда необязательный)
    await _show_soft_cta(msg, custom_cta_message=CTA_MESSAGE)


# Добровольная команда для вызова CTA вручную
@router.message(Command("subscribe"))
async def cmd_subscribe(msg: Message) -> None:
    await _show_soft_cta(msg, custom_cta_message=CTA_MESSAGE)


@router.callback_query(F.data == CB_CTA_PROMPT)
async def cb_cta_prompt(cb: CallbackQuery) -> None:
    # Если хотите вызывать из других мест — этот хэндлер просто рисует CTA.
    await _show_soft_cta(cb.message, custom_cta_message=CTA_MESSAGE)
    await cb.answer()


@router.callback_query(F.data == CB_CTA_CHECK)
async def cb_cta_check(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    ok = await _is_user_subscribed(cb.bot, user_id)
    if ok:
        await cb.message.edit_text(
            "✅ Спасибо за подписку! Погнали 👇",
            reply_markup=None,
            disable_web_page_preview=True,
        )
        await cb.answer("Подписка подтверждена 🙌")
        roots = await get_children_cached(None)
        await cb.bot.send_message(
            chat_id=cb.from_user.id,
            text="Выбирай страну, о которой хочешь узнать полезную информацию:",
            reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
            disable_web_page_preview=True
        )
    else:
        await cb.message.edit_text(
            (
                "Похоже, подписка пока не оформлена.\n\n"
                "1) Нажми «Открыть канал» и подпишись\n"
                "2) Вернись сюда и жми «Я подписался»"
            ),
            reply_markup=build_soft_cta_kb(include_skip=True),
            disable_web_page_preview=True,
        )
        await cb.answer("Подписка не найдена. Попробуй ещё раз после подписки.", show_alert=False)


@router.callback_query(F.data == CB_CTA_SKIP)
async def cb_cta_skip(cb: CallbackQuery) -> None:
    await cb.message.edit_text(
        "✅ Как скажешь! Погнали 👇",
        reply_markup=None,
        disable_web_page_preview=True,
    )
    roots = await get_children_cached(None)
    await cb.bot.send_message(
        chat_id=cb.from_user.id,
        text="Выбирай страну, о которой хочешь узнать полезную информацию:",
        reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.callback_query(F.data.startswith("open_"))
async def cb_open(cb: CallbackQuery) -> None:
    item_id = int(cb.data.removeprefix("open_"))
    item = await get_content_cached(item_id)
    # logger.info(f"Got {item}, parent_id = {getattr(item, 'parent_id', None)}")
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb_cached(item_id)
    breadcrumb = _clean_for_btn_cached(build_breadcrumb_text_cached(breadcrumb_items))

    children = await get_children_cached(item.id)
    if children:  # category
        # logger.info(f"item: {item}")
        await cb.message.edit_text(
            f"📂 <b>{breadcrumb}</b>",
            reply_markup=build_children_kb(children, parent_id=item.parent_id),
            disable_web_page_preview=True
        )
        await cb.answer()
        return

    # Split long text (TG limit 4096)
    # logger.info(f"item: {item}")
    # logger.info(f"message: {cb.message.message_id}")

    complete_text, extra_chunks = render_leaf_message_cached(item, breadcrumb_items)

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
    roots = await get_children_cached(None)
    await cb.message.edit_text(
        "Выбирай страну, о которой хочешь узнать полезную информацию:",
        reply_markup=build_children_kb(roots, parent_id=None, main_menu=True),
        disable_web_page_preview=True
    )
    await cb.answer()


@router.callback_query(F.data.startswith("back_"))
async def cb_back(cb: CallbackQuery) -> None:
    parent_id = int(cb.data.removeprefix("back_"))
    siblings = await get_children_cached(parent_id)
    parent_obj = await get_content_cached(parent_id) if parent_id else None
    breadcrumb_items = await get_breadcrumb_cached(parent_id)
    breadcrumb = _clean_for_btn_cached(build_breadcrumb_text_cached(breadcrumb_items))
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
    item = await get_content_cached(item_id)
    # logger.info(f"Got {item}, parent_id = {getattr(item, 'parent_id', None)}")
    if not item:
        await cb.answer("⚠️ Запись не найдена.", show_alert=True)
        return

    breadcrumb_items = await get_breadcrumb_cached(item_id)
    complete_text, extra_chunks = render_leaf_message_cached(item, breadcrumb_items)

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
#     # logger.info("msg_search: query=%r from user=%s", query, msg.from_user.id)
#
#     no_results = True
#     async for item, score in search_content(query, top_k=1):
#         # logger.debug("search hit: id=%s score=%s", item.id, score)
#
#         breadcrumb_items = await get_breadcrumb_cached(item.id)
#         breadcrumb = _clean_for_btn_cached(" › ".join(i.title for i in breadcrumb_items))
#
#         raw_body = item.body or ""
#
#         safe_body = safe_html(raw_body)
#         chunks = [remove_seo_hashtags(c).strip() for c in split_html_safe(safe_body, max_len=3800)]
#
#         if chunks:
#             snippet_html = f"\n\n{chunks[0]}"
#         else:
#             # logger.warning(f"Empty body for content id={item.id}")
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
