# tgbot‑nakama – Project Overview (v0.2.x)

## 1  Goal

Create a **Telegram bot** that delivers Russian‑language reference content through an intuitive **inline‑button menu** and fast **semantic search**. Content is authored in Google Docs by editors and automatically ingested, embedded and served to end‑users – no manual CMS inside the bot is required.

---

## 2  Key Features (Current)

| # | Feature                      | Details                                                                                                                                                                                                                                                                         |
| - |------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | **Nested inline menus**      | Tree navigation built on PostgreSQL `content` table (`parent_id`, `ord`). "⬅️ Назад" / "🏠 Главная" buttons for smooth UX.                                                                                                                                                      |
| 2 | **Google Docs → DB loader**  | Service‑account pull of a structured Google Doc (H1/H2/H3), parsing into a hierarchical list, wiping old content, bulk‑inserting new. Runs automatically at every bot startup.                                                                                                  |
| 3 | **Vector search**            | `intfloat/multilingual‑e5‑small` ONNX model generates embeddings; vectors stored in **Qdrant** (`content_vectors` collection, cosine distance). `user_router` intercepts free‑text messages, queries top‑3 hits, returns snippets + “📖 Читать полностью” button (`open_<id>`). |
| 4 | **Async, typed backend**     | Python 3.11, **Aiogram 3.x**, asyncpg, qdrant‑client, Pydantic Settings. Fully asynchronous I/O; heavy embedding inference off‑loaded to thread pool.                                                                                                                           |
| 5 | **Robust startup & logging** | Loguru logging; try/except around startup; uncaught exceptions sent to admin chat (ID `231584958`); graceful shutdown.                                                                                                                                                          |
| 6 | **Dual runtime modes**       | *Local* → long‑polling; *Production* → webhook via `aiohttp` (`AppRunner`, `TCPSite`) with `WEBHOOK_SECRET` validation.                                                                                                                                                         |
| 7 | **DevOps & CI**              | Docker Compose (`bot`, `postgres`, `qdrant`); automatic Alembic migrations; GitHub Actions pipeline – Black, Ruff, Pytest (Testcontainers Postgres), Docker build.                                                                                                              |

---

## 3  Architecture

```
┌─────────────┐    startup loader   ┌──────────────┐
│ Google Doc  │ ──────────────────▶ │ PostgreSQL   │
└─────────────┘                    └──────────────┘
        │  embeddings                       ▲
        ▼                                   │ SQL (async)
┌──────────────────┐     upsert/search      │
│ ONNX Embedding   │ ─────────────────────▶ │ Qdrant        │
└──────────────────┘                        └──────────────┘
        ▲                                         ▲
        │ (threadpool)                            │ vectors
        │                                         │
        └───────────  Aiogram 3.x  ───────────────┘
                           │
                           ▼
                     Telegram Users
```

*►  No inline/admin CMS:* Editors simply update the Google Doc; redeploy/restart the bot to reflect changes. This choice cut significant complexity and matched the team’s workflow.

---

## 4  Milestones & Status

| Version   | Date       | Milestone              | Highlights                                                                                      |
| --------- | ---------- |------------------------| ----------------------------------------------------------------------------------------------- |
| **0.0.6** | 2025‑06‑01 | *Foundation*           | DB schema, async DAO, project scaffolding, CI, Docker skeleton.                                 |
| **0.0.7** | 2025‑06‑01 | *User Navigation*      | `/start`, `/help`, inline menu, Testcontainers tests.                                           |
| **0.0.8** | 2025‑06‑01 | *Google Doc Ingestion* | End‑to‑end loader, content refresh on boot; removed demo seeder.                                |
| **0.0.9** | 2025‑06‑01 | *Container Hardening*  | Deb‑slim image, webhook envs, automatic migrations, structured logging.                         |
| **0.1.0** | 2025‑06‑02 | *Startup Diagnostics*  | Fatal error alerts to admin; refactored polling vs webhook logic.                               |
| **0.2.0** | 2025‑06‑05 | *Semantic Search*      | Qdrant integration, multilingual embeddings, top‑3 answer UI; widened `title` column to `TEXT`. |

---

## 5  Upcoming Work (0.3.x+)

1. **Health & Metrics** – Prometheus exporter, /healthz endpoint, Grafana dashboard.
2. **Hot reload of Google Doc** – schedule incremental sync every X hours instead of reboot‑only.
3. **Horizontal scaling** – optional multiple bot instances (webhook) with shared Postgres/Qdrant.
4. **Caching** – in‑memory cache for top‑level menu & popular articles.
5. **i18n groundwork** – store `lang` column, allow future English content.

*Admin inline CMS has been formally **dropped** in favour of Google Docs authoring workflow.*

---

## 6  Quick Start

```bash
# 1. Build & start services
$ docker compose up -d postgres qdrant bot

# 2. (first run) Apply migrations is automatic at container entry.

# 3. Point BotFather webhook to https://<domain>/<WEBHOOK_PATH>?secret=<WEBHOOK_SECRET>
```

---

© 2025 Nomado-Nakama team
