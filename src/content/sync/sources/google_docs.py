from __future__ import annotations

import base64
import html
import json
import re
from html import escape
from time import perf_counter
from typing import Iterable, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from loguru import logger

from src.config import settings


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
    parts: list[str] = []
    for el in elems:
        tr = el.get("textRun")
        if tr:
            parts.append(_run_to_html(tr))
    return "".join(parts)


def fetch_document(doc_id: str) -> Tuple[str, str]:
    """
    Fetch Google Doc and convert paragraphs to a single string with our H1/H2/H3/H4 markers.
    Returns: (rendered_text_lines, revision_id)
    """
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

        line = _elements_to_html(para.get("elements", [])).rstrip()

        if line:
            if prefix:
                clean = re.sub(r"<[^>]+>", "", line)
                clean = html.unescape(clean).strip()
                result_lines.append(f"{prefix}{clean}")
            else:
                result_lines.append(line)

    logger.debug(
        "Google Doc fetched in {:.2f}s — {} lines (H1 {}, H2 {}, H3 {}, H4 {})",
        perf_counter() - t0,
        len(result_lines),
        heading_counter["H1"],
        heading_counter["H2"],
        heading_counter["H3"],
        heading_counter["H4"],
    )
    return "\n".join(result_lines), document["revisionId"]
