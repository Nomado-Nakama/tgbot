from src.bot.content_dao import Content
from src.bot.keyboard import ROOT_BACK_ID, build_children_kb


def fake(id_: int, title: str) -> Content:
    return Content(id=id_, parent_id=None, title=title, body=None, ord=0, text_digest="", embedded_at=None)


def test_build_root_kb():
    kb = build_children_kb([fake(1, "A"), fake(2, "B")], parent_id=None)
    buttons = [b.text for row in kb.inline_keyboard for b in row]
    assert buttons == ["A", "B", "⬅️ Назад", "🏠 Главная"]
    # no back button at root
    assert ROOT_BACK_ID in [b.callback_data for b in kb.inline_keyboard[-1]]
