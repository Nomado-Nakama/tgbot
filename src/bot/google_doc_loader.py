import base64
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from loguru import logger


from src.bot.config import settings
from src.bot.embeddings import generate_embedding
from src.bot.content_dao import (
    insert_node,
    parse_google_doc_text_as_list_of_content_nodes,
    remove_all_content,
)
from src.bot.qdrant_high_level_client import client, QDRANT_COLLECTION


def load_google_doc(doc_id: str) -> str:
    """Fetch styled text from a Google Doc and mark headers with H1:/H2:/H3: prefixes."""
    creds_dict = json.loads(
        base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_BASE64).decode("utf-8")
    )
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/documents.readonly"],
    )
    service = build("docs", "v1", credentials=creds)
    document = service.documents().get(documentId=doc_id).execute()

    result_lines = []

    for element in document.get("body", {}).get("content", []):
        para = element.get("paragraph")
        if not para:
            continue

        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        prefix = ""
        if style == "HEADING_1":
            prefix = "H1:"
        elif style == "HEADING_2":
            prefix = "H2:"
        elif style == "HEADING_3":
            prefix = "H3:"

        line = ""
        for elem in para.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                line += text_run.get("content", "")

        line = line.strip()
        if line:
            result_lines.append(f"{prefix}{line}" if prefix else line)

    return "\n".join(result_lines)


async def reload_content_from_google_docx_to_db():
    raw_content_from_google_docs = load_google_doc(
        doc_id=settings.FULL_CONTENT_GOOGLE_DOCS_URL.split("/")[-1],
    )
    logger.info("🔄 Parsing google doc into content nodes...")
    top_nodes = parse_google_doc_text_as_list_of_content_nodes(raw_content_from_google_docs)
    logger.info("✅ Parsed")

    logger.info("📥 Removing all old content from DB...")
    await remove_all_content()

    logger.info("📥 Inserting into DB...")
    for i, node in enumerate(top_nodes):
        content_id = await insert_node(node, parent_id=None, order=i)
        logger.info(f"📥 {content_id} inserted into DB...")
        if node.body:
            vector = await generate_embedding(node.body)
            await client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=[
                    {
                        "id": content_id,
                        "vector": vector,
                        "payload": {"title": node.title},
                    }
                ],
            )

    logger.info("✅ All content nodes inserted...")
