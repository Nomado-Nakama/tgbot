import json
import base64
from datetime import datetime, timezone
from html import escape
from time import perf_counter
from typing import Iterable, List, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from loguru import logger

from src.bot.config import settings
from src.bot.db import fetchrow, execute as pg_execute, fetch

from src.bot.embeddings import generate_embeddings

from src.bot.content_dao import (
    parse_google_doc_text_as_list_of_content_nodes,
    ContentNode,
)
from src.bot.qdrant_high_level_client import client, QDRANT_COLLECTION

from qdrant_client.http.models import PointStruct, PointIdsList

from src.bot.utils_hash import digest

_HTML_SAFE_RUN_KEYS = ("bold", "italic", "underline", "strikethrough")


class GoogleDocLoader:

    def __init__(self):
        self.embed_candidates: List[Tuple[int, str, str, bool]] = []
        self.seen_ids: set[int] = set()

    @staticmethod
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

    def _elements_to_html(self, elems: Iterable[dict]) -> str:
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
            parts.append(self._run_to_html(text_run))
        return "".join(parts)

    def load_google_doc(self, doc_id: str) -> str:
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

            line = self._elements_to_html(para.get("elements", [])).rstrip()
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
        return "\n".join(result_lines), document["revisionId"]

    async def _upsert_node(
            self,
            node: ContentNode, parent_id: int | None, ord_: int
    ) -> int:  # returns id
        txt = node.body or node.title  # what we feed into the encoder
        dg = digest(txt)

        # look for an existing row with the same natural key (parent_id, ord)
        row = await fetchrow(
            """
                SELECT id, text_digest, parent_id, ord
                  FROM content
                 WHERE parent_id IS NOT DISTINCT FROM $1
                   AND ord = $2;
                """,
            parent_id,
            ord_,
        )

        if row is None:
            # --- insert new row ------------------------------------------------
            inserted = await fetchrow(
                """
                    INSERT INTO content (parent_id, title, body, ord,
                                         text_digest, embedded_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id;
                    """,
                parent_id,
                node.title,
                node.body,
                ord_,
                dg,
                datetime.now(tz=timezone.utc),
            )
            cid = inserted["id"]
            self.embed_candidates.append((cid, txt, node.title, bool(node.body)))

        else:
            cid = row["id"]
            unchanged = row["text_digest"] == dg
            # If digest changed → UPDATE + re-embed
            if not unchanged:
                await pg_execute(
                    """
                        UPDATE content
                           SET title       = $2,
                               body        = $3,
                               text_digest = $4,
                               embedded_at = $5
                         WHERE id = $1;
                        """,
                    cid,
                    node.title,
                    node.body,
                    dg,
                    datetime.now(tz=timezone.utc),
                )
                self.embed_candidates.append((cid, txt, node.title, bool(node.body)))

            # Even if digest is the same the node may have moved in the tree
            if row["parent_id"] != parent_id or row["ord"] != ord_:
                await pg_execute(
                    "UPDATE content SET parent_id = $2, ord = $3 WHERE id = $1;",
                    cid,
                    parent_id,
                    ord_,
                )

        self.seen_ids.add(cid)

        # recurse into children
        for idx, child in enumerate(node.children):
            await self._upsert_node(child, cid, idx)

        return cid

    async def reload_content_from_google_docx_to_db(self) -> None:
        raw, new_rev = self.load_google_doc(settings.FULL_CONTENT_GOOGLE_DOCS_URL.split("/")[-1])

        prev_rev_row = await fetchrow("SELECT value FROM kv WHERE key = 'doc_revision';")
        prev_rev = prev_rev_row["value"] if prev_rev_row else ""

        points_exist = await client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=None,
            with_payload=False,
            limit=1
        )
        logger.info(f"count {QDRANT_COLLECTION}: {await client.count(collection_name=QDRANT_COLLECTION)}")
        logger.info(f"points_exist: {points_exist}")

        if not points_exist[0]:  # collection is empty
            logger.warning("🆕 Empty Qdrant collection detected – forcing full re-index")
            prev_rev = "totally_nonexistent_revision"  # pretend revision changed

        if new_rev == prev_rev:
            logger.info("🟢 Google Doc revision unchanged – skipping synchronisation.")
            return

        # Update cached revision *early* so crashes don’t cause infinite loops
        await pg_execute(
            "UPDATE kv SET value = $1 WHERE key = 'doc_revision';",
            new_rev,
        )

        logger.info("🔄 Parsing google doc into content nodes …")
        top_nodes = parse_google_doc_text_as_list_of_content_nodes(raw)
        logger.info(f"✅ Parsed — {len(top_nodes)} top-level nodes")

        logger.info("🚀 Inserting nodes into DB …")

        for idx, root in enumerate(top_nodes):
            await self._upsert_node(root, None, idx)

        # ── 4. Delete rows that disappeared from the document (optional) ─────────
        all_row_ids = {r["id"] for r in await fetch("SELECT id FROM content;")}
        to_delete = all_row_ids - self.seen_ids
        if to_delete:
            await pg_execute(
                "DELETE FROM content WHERE id = ANY($1::bigint[]);",
                list(to_delete),
            )
            # Remove corresponding vectors from Qdrant
            await client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=PointIdsList(points=list(to_delete)),
            )
            logger.info(f"🗑️  Deleted {len(to_delete)} obsolete rows")

        logger.info(f"self.embed_candidates: {len(self.embed_candidates)}")
        # ── 5. Re-embed & upsert only the changed/new rows into Qdrant — fast! ───
        if not self.embed_candidates:
            logger.success("🟢 No content changes that require new embeddings.")
            return

        texts = [item[1] for item in self.embed_candidates]
        vectors = generate_embeddings(texts)
        points = [
            PointStruct(
                id=cid,
                vector=[float(x) for x in vec],
                payload={"title": title, "has_body": has_body},
            )
            for (cid, _txt, title, has_body), vec in zip(self.embed_candidates, vectors)
        ]

        await client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        logger.success(f"✅ Upserted {len(points)} vectors into Qdrant")
