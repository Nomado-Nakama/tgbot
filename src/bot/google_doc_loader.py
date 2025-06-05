import json
import base64
from html import escape
from time import perf_counter
from typing import Iterable

from google.oauth2 import service_account
from googleapiclient.discovery import build
from loguru import logger

from src.bot.config import settings

from src.bot.embeddings import generate_embeddings

from src.bot.content_dao import (
    insert_node,
    parse_google_doc_text_as_list_of_content_nodes,
    remove_all_content,
    ContentNode,
)
from src.bot.qdrant_high_level_client import client, QDRANT_COLLECTION
from qdrant_client.http.models import PointStruct

_HTML_SAFE_RUN_KEYS = ("bold", "italic", "underline", "strikethrough")


def _run_to_html(run: dict) -> str:
    """Convert one Docs textRun to Telegram-safe HTML."""
    txt = escape(run.get("content", ""))
    style = run.get("textStyle", {})

    if style.get("bold"):
        txt = f"<b>{txt}</b>"
    if style.get("italic"):
        txt = f"<i>{txt}</i>"
    if style.get("underline"):
        txt = f"<u>{txt}</u>"
    if style.get("strikethrough"):
        txt = f"<s>{txt}</s>"

    link = style.get("link", {}).get("url")
    if link:
        txt = f'<a href="{escape(link)}">{txt}</a>'

    return txt


def _elements_to_html(elems: Iterable[dict]) -> str:
    """
    Join all paragraph elements into one HTML string.

    NB: `elems` is a list of *ParagraphElement* objects; each element may or
    may not contain a "textRun".  We need the inner dict, not the wrapper.
    """
    parts: list[str] = []
    for el in elems:
        text_run = el.get("textRun")
        if not text_run:  # skip images, page-breaks, etc.
            continue
        parts.append(_run_to_html(text_run))
    return "".join(parts)

def load_google_doc(doc_id: str) -> str:
    t0 = perf_counter()
    creds_info = json.loads(base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_BASE64))
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/documents.readonly"]
    )
    service = build("docs", "v1", credentials=creds, cache_discovery=False)
    document = service.documents().get(documentId=doc_id).execute()

    result_lines: list[str] = []
    heading_counter = {"H1": 0, "H2": 0, "H3": 0, "H4": 0}

    for elem in document.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue

        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        prefix = ""
        if style == "HEADING_1":
            prefix, heading_counter["H1"] = "H1:", heading_counter["H1"] + 1
        elif style == "HEADING_2":
            prefix, heading_counter["H2"] = "H2:", heading_counter["H2"] + 1
        elif style == "HEADING_3":
            prefix, heading_counter["H3"] = "H3:", heading_counter["H3"] + 1
        elif style == "HEADING_4":
            prefix, heading_counter["H4"] = "H4:", heading_counter["H4"] + 1

        line = _elements_to_html(para.get("elements", [])).strip()

        line = line.strip()
        if line:
            result_lines.append(f"{prefix}{line}" if prefix else line)

    logger.debug(
        "Google Doc fetched in {:.2f}s — {} lines (H1 {}, H2 {}, H3 {}, H4 {})",
        perf_counter() - t0,
        len(result_lines),
        heading_counter["H1"],
        heading_counter["H2"],
        heading_counter["H3"],
        heading_counter["H4"],
    )
    return "\n".join(result_lines)


# trimmed – only the essential changes
async def reload_content_from_google_docx_to_db() -> None:
    raw = load_google_doc(settings.FULL_CONTENT_GOOGLE_DOCS_URL.split("/")[-1])

    logger.info("🔄 Parsing google doc into content nodes …")
    top_nodes = parse_google_doc_text_as_list_of_content_nodes(raw)
    logger.info(f"✅ Parsed — {len(top_nodes)} top-level nodes")

    logger.info("📥 Removing old content from DB …")
    await remove_all_content()

    logger.info("🚀 Inserting nodes into DB …")
    collected: list[tuple[int, ContentNode]] = []
    for ord_, n in enumerate(top_nodes):
        await insert_node(n, parent_id=None, order=ord_, collected=collected)

    # ---------------------------------------------------------------------
    # Build embedding batch (body if present else title) -------------------
    # ---------------------------------------------------------------------
    good_nodes = [(cid, n) for cid, n in collected if (n.body or n.title)]
    if not good_nodes:
        logger.warning("🔎 No text to embed – skipping Qdrant upsert")
        return

    texts = [n.body or n.title for _, n in good_nodes]
    vectors = generate_embeddings(texts)

    points = [
        PointStruct(
            id=cid,
            vector=[float(x) for x in vec],  # make 100 % sure every item is native float
            payload={"title": n.title, "has_body": bool(n.body)},
        )
        for (cid, n), vec in zip(good_nodes, vectors)
    ]
    if not points:
        logger.warning("🔎 No vectors to upsert – skipping Qdrant call")
        return

    await client.upsert(collection_name=QDRANT_COLLECTION, points=points)

    logger.success(f"✅ Upserted {len(points)} vectors into Qdrant")

    logger.info("✅ All content nodes inserted...")
