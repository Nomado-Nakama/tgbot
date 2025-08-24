## [0.0.6] – 2025-06-01

### Added
- ✅ **Content Table & Hierarchical Navigation**
  - PostgreSQL `content` table with `parent_id`, `title`, `body`, `ord`, `created_at`
  - Alembic migration for initial schema (`0e7a8abff60d_create_content_table`)
  - Async DAO helpers in `content_dao.py`: `get_children`, `get_content`
  - Integration test for `get_children` with PostgreSQL cleanup logic

- 🤖 **Telegram Bot Core (Aiogram 3.x)**
  - Basic `/ping` command with DB connectivity check
  - Dispatcher setup with long polling for local dev mode
  - Full environment config via `.env` and `pydantic-settings`

- 🔧 **Database Layer (Async)**
  - PostgreSQL async connection pool via `asyncpg`
  - Helpers: `fetchrow`, `fetch`, `execute` with connection context manager

- 🛠️ **Project Configuration & Tooling**
  - `pyproject.toml` with project metadata and dependencies
  - Formatted with **Black**, linted with **Ruff**
  - Python version: 3.12 (in `.python-version`)
  - Git ignored: `.venv`, `.env`, `.pyc`, logs

- 🐳 **Docker & DevOps**
  - `docker-compose.yaml` with `bot` service (uses `.env` for ports/env)
  - GitHub Actions CI (`ci.yml`) that runs Alembic migration

- 📁 **Code Structure & Logging**
  - Modular bot structure in `src/bot`
  - Centralized logging setup with Loguru (file + console handlers)

- 📄 **Documentation**
  - `project_overview.md` with detailed implementation plan and milestones
  - Change log initialized with v0.0.6

### Notes
- Project renamed to `tgbot-nakama`
- All components are structured with production in mind (async DB, CI, logs, etc.)
- Ready for milestone 1: user-facing inline navigation and admin content management

---

## [0.0.7] – 2025-06-01

### Added
- **User‐facing navigation**  
  - `/start` and `/help` commands send a welcome message (in Russian) and display the top-level content menu.  
  - Inline callback handlers for:
    - `open_<id>`: open a category or article by its content ID.  
    - `back_<parent_id>`: go up one level in the hierarchy.  
    - `back_root`: return to the main menu from any level.  
  - Splitting of long article text into 4 000-character chunks to avoid Telegram’s 4 096-character limit.

- **`keyboard.py` helper**  
  - Pure‐function `build_children_kb(children: list[Content], *, parent_id: int | None) → InlineKeyboardMarkup`  
    • Renders one button per child item, plus “⬅️ Назад” (if not at root) and “🏠 Главная” (always present).  
    • Returns a ready-to-use `InlineKeyboardMarkup` with proper `callback_data` values.

- **`user_router.py` module**  
  - All public (non-admin) handlers moved out of `main.py` into a dedicated `Router(name="user")`.  
  - Registered in `main.py` via `dp.include_router(user_router)`—keeps code modular and testable.

- **Unit tests**  
  - New `tests/test_keyboard.py` to verify the structure and button texts of the root keyboard.  
  - End-to-end “happy-path” for `get_children(None)` in `tests/test_content_dao.py` now runs against Testcontainers’ ephemeral Postgres.

- **Testcontainers Postgres fixture**  
  - In `tests/conftest.py`, replaced any reliance on a live database with a `PostgresContainer("postgres:16-alpine")`.  
  - `init_pool(postgres_url=…)` is called with the container’s connection URL, ensuring isolation and repeatability.

- **Demo seeding script**  
  - `scripts/seed_demo.py` inserts a small hierarchy (“Европа” → “Франция”, “Испания”; “Азия”) so that local development and CI aren’t empty.

- **Docker Compose enhancements**  
  - Added a `db` service (Postgres 16-alpine) with a healthcheck.  
  - `bot` service now `depends_on: db` (condition: service_healthy).  
  - Postgres port mapped to host `9441:5432` (for local inspection, if needed).

- **CI pipeline updates**  
  - `.github/workflows/ci.yml` now:
    1. Installs dev+test dependencies (`pip install -e .[test]`).  
    2. Runs `alembic upgrade head`.  
    3. Executes `pytest -q`.  

### Changed
- **`main.py` updates**  
  - Imported and registered `user_router` instead of placing all handlers inline.  
  - Adjusted `init_pool()` signature to accept an optional `postgres_url` (used by Testcontainers).

- **DAO tests**  
  - Removed reliance on “runs safely against a non-empty prod DB.” Now always uses Testcontainers.

- **`docker-compose.yaml`**  
  - Bumped Postgres to `postgres:16-alpine` and exposed port 9441.  
  - Removed placeholder “data” for the `bot` service—now fully wired with `db`.

- **Documentation**  
  - Appended a new “0.0.7” section to `docs/CHANGELOG.md`.  
  - Added instructions for `scripts/seed_demo.py` to `CHANGELOG` and `README.md`.

### Removed / Deprecated
- **Live-DB testing** in `tests/test_content_dao.py` (no longer necessary; replaced by Testcontainers).  

---

## \[0.0.8] – 2025-06-01

### Added

* **Google Docs integration**

  * New module `google_doc_loader.py` fetches a Google Doc using a service account, parses text based on heading styles, and auto-populates the database with a hierarchical structure.
  * Heading structure levels:

    * `H1:` (countries)
    * `H2:` (topics)
    * `H3:` (questions)
    * Body text beneath `H3` becomes article content.
  * `reload_content_from_google_docx_to_db()` automates the whole flow: fetch → parse → wipe old → insert new.

* **Env & config additions**

  * New `.env` vars:

    * `GOOGLE_SERVICE_ACCOUNT_BASE64` – your service account JSON (base64-encoded)
    * `FULL_CONTENT_GOOGLE_DOCS_URL` – link to the source document
  * Added to `.env.example` and parsed via `settings.py`.

* **Content parsing + seeding**

  * `ContentNode` structure now lives in `content_dao.py`, with:

    * `insert_node()` – recursive tree insert
    * `remove_all_content()` – truncate all content
    * `parse_google_doc_text_as_list_of_content_nodes()` – build tree from parsed text
  * Full seeding triggered automatically from `main.py` on bot startup (`await reload_content_from_google_docx_to_db()`).

* **Dependencies**

  * Added optional \[google] dependencies to `pyproject.toml`:

    * `google-api-python-client`
    * `google-auth`
    * `google-auth-httplib2`
    * `google-auth-oauthlib`

### Changed

* **Startup process**

  * `main.py` now calls `reload_content_from_google_docx_to_db()` before starting the bot. This ensures the latest content is loaded from Google Docs every time the bot restarts.

* **`.gitignore`**

  * Excludes `google-service-account.json` as a safeguard, even though it's not used directly (base64 only).

* **`.env.example`**

  * Includes placeholder values for the new Google Docs integration variables.

* **Database utils**

  * `fetch`, `execute` now accept `**kwargs` to support future extensions (e.g. query timeouts or custom connection args).

### Removed

* 🗑️ Deleted legacy `scripts/seed_demo.py` (and its `__init__.py`) which previously inserted static placeholder content.

---

## \[0.0.9] – 2025-06-01

### Added

* **Docker enhancements**

  * Added `.dockerignore` to optimize Docker image builds by excluding unnecessary files.
  * Defined explicit Docker network (`bot-network`) in `docker-compose.yaml` to improve inter-service communication.
  * Included environment variable `PYTHONUNBUFFERED=1` in Dockerfile for real-time logging.
  * Introduced automatic Alembic migrations (`alembic upgrade head`) to run at container startup via Docker Compose.
  * Added `WEBHOOK_SECRET` to `.env.example` and `config.py` for webhook security.

### Changed

* **Dockerfile improvements**

  * Switched from Alpine to Debian-based slim Python image (`python:3.12-slim-bookworm`) for enhanced compatibility.
  * Updated UV installer method for reproducible setup.
  * Improved clarity and maintainability of Dockerfile commands.

* **Logging configuration**

  * Adjusted `logger.py` to explicitly log to `sys.stdout` with queued logging for better container visibility.

* **Project configuration**

  * Added explicit `WEBHOOK_PATH` to `config.py` for webhook route management.
  * Adjusted Alembic migration imports to comply with modern Python (`collections.abc`).

### Removed

* 🗑️ Deprecated Alpine-based Docker image (`python:3.12-alpine`).
* 🗑️ Removed legacy and unnecessary `requirements.txt` in favor of consistent dependency management via `pyproject.toml`.

---

Here is the changelog entry for version `0.1.0`, based on your provided diff:

---

## \[0.1.0] – 2025-06-02

### Added

* **Startup exception handling**

  * Wrapped the entire bot startup sequence in a `try` block.
  * Logs any unhandled exceptions with full traceback using `logger.exception(...)`.
  * Sends a formatted error message to a Telegram admin (`chat_id=231584958`) if startup fails.
  * Ensures that crashes in `main()` or webhook setup are surfaced and actionable.

* **Webhook server bootstrap**

  * Replaced unused `web.run_app(...)` with explicit setup via `AppRunner` and `TCPSite`:

    * Manually starts `aiohttp` server on `WEBAPP_HOST:WEBAPP_PORT`.
    * Logs successful startup URL with `logger.success(...)`.
    * Keeps the server running via `await asyncio.Event().wait()`.

### Changed

* **Environment-based logic refactor**

  * Reorganized `main.py` to clearly separate LOCAL (long polling) vs PROD (webhook server) behavior.
  * All webhook logic moved under the `else:` block guarded by `RUNNING_ENV`.
  * Local mode logs cleaner startup message and exits on exception.

* **Logging improvements**

  * Logs uncaught exceptions with a complete stack trace using `traceback.format_exc()`.
  * On fatal crash, also logs with `logger.critical(..., exc_info=True)` in `__main__` block.

### Notes

* Makes production-ready error handling a first-class part of the bot lifecycle.
* Admin alert ensures visibility for critical failures, especially during early deployments.

## [0.2.0] – 2025-06-05

### Added
- **🔍 Semantic search stack**
  * Integrated **Qdrant** as a vector-database (`qdrant_high_level_client.py`, `search_service.py`).
  * Free-text queries now handled in `user_router.py`; returns the top-3 semantically-relevant answers with a “📖 Читать полностью” button.

- **🧠 Multilingual embeddings**
  * New `embeddings.py` uses `intfloat/multilingual-e5-small` (ONNX, CPU); warmed up in a thread-pool for fast inference.
  * Dockerfile pre-downloads the model to keep first-run latency near zero.

- **⚡ Automated vector ingestion**
  * `google_doc_loader.py` now:
    1. Parses the Google Doc as before.
    2. Generates embeddings for every node (`title + body`).
    3. Upserts them to Qdrant with payload `{title, has_body}`.

- **🐳 Docker & Compose**
  * Added dedicated **`qdrant`** service + `qdrant-data` volume.
  * `bot` service now passes `QDRANT_HOST` / `QDRANT_PORT` and updated `POSTGRES_URL`.
  * `.gitignore` excludes `docker-compose.override.yaml`.

- **📦 Dependencies / runtime**
  * Added `torch`, `sentence-transformers[onnx]`, `qdrant-client[fastembed]`, `huggingface-hub[hf-xet]`.
  * Extra PyPI index for CPU-only PyTorch wheels.
  * Lowered minimum Python to **3.11** for ONNX compatibility.

- **🛠️ DB migrations**
  * New alembic revision `2df6976e3c09_title_to_text` – `content.title` widened from `VARCHAR(100)` to `TEXT`.

- **🔔 Robust startup diagnostics**
  * `main.py` now ensures the Qdrant collection exists before loading content.
  * On critical failure the full traceback is written to `alert.txt` **and** sent to the admin as a file.

### Changed
- `insert_node()` now accepts a `collected` accumulator, letting the loader gather **all** inserted nodes in one pass.
- `logger.py` resolves `LOG_PATH` relative to `project_root_path` (fixes missing-logs in Docker).
- Dockerfile exposes new optional tuning envs (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `TRANSFORMERS_OFFLINE`).

### Removed / Deprecated
- None.

### Breaking changes
1. A running **Qdrant** instance is now required.  
   → Run `docker compose up qdrant postgres` before launching the bot.
2. Embedding model is now loaded **offline** from disk.  
   → You must pre-download `intfloat/multilingual-e5-small` and place it in `src/models/intfloat/multilingual-e5-small`.  
     Use `transformers-cli` or run the model loader once with internet access:
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer("intfloat/multilingual-e5-small")
   model.save("./src/models/intfloat/multilingual-e5-small")
   ```
3. Alembic migration required:
   ```bash
   alembic upgrade head
   ```

## [0.3.1] – 2025-07-15

### Added
- 🧠 **LLM helper tasks in `tools/dcl.ps1`** – generator now embeds the latest
  commit message and current `CHANGELOG.md` into `<llm_task>` nodes
  (`type="commit_message"` / `"changelog_update"`) to speed AI-assisted release
  notes.
- 🧵 **Multi-line commit capture** – collects full body via `git log -1 --pretty=%B`.
- 📄 **CHANGELOG capture** – reads `docs/CHANGELOG.md` when present (falls back to
  empty string).

### Changed
- ✏️ Normalized UTF-8 locale export (`$env:LC_ALL = 'C.UTF-8'`) and cleaned
  comments.
- 🧹 Removed stray diagnostic suffix from root XML element assignment comment.
- 🧾 Dropped trailing `Export-ModuleMember`; function remains usable when
  dot-sourced and reduces noise.
- 📝 **Docs:** major rewrite of `docs/project_overview.md` → concise
  *tgbot-nakama – Project Overview (v0.2.x)* summarizing current architecture
  (Google Docs ingestion replaces inline admin CMS), key features table,
  milestone history, upcoming work list, and quick-start instructions.

### Removed
- ❌ Legacy inline/admin CMS implementation plan (workflow now Google Docs
  source-of-truth).
- ❌ Misc stray placeholder/comments in PowerShell helper.

### Notes
- No application runtime or DB schema changes in this release; documentation +
  tooling only.
- Tagged from `v0.3.0` → patch bump per SemVer; pre-1.0 API remains unstable.

## [0.3.2] – 2025-07-17

### Added
- **Docker migrator** stage: runs `alembic upgrade head` once and exits.
- BuildKit hard-link optimisation (`COPY --link`) and cache mounts for
  both `apt` and `uv` dramatically cut rebuild times.

### Changed
- **Dockerfile**
  - Switched to BuildKit syntax (`# syntax=docker/dockerfile:1.7`).
  - Single-curl installation of **uv**; dependency layer built from
    `pyproject.toml` + `uv.lock` with `--no-dev`.
  - PyTorch now pulled from the official CPU-only index.

- **docker-compose.yaml**
  - Network renamed to `bot-net`; qdrant kept internal (no host port).
  - Added `migrator` service; `bot` waits for successful migration via
    `depends_on.condition: service_completed_successfully`.
  - Healthcheck for Postgres now uses `${POSTGRES_USER}`.

- **Bot runtime**
  - Global error handler updated to new `ErrorEvent` API; richer logging.
  - Search snippet generation hardened against empty / malformed HTML.

### Removed
- Host-level qdrant port mapping (`6333:6333`).
- Compose-level CPU / memory limits that interfered with CI.

### Breaking
- External references to the old network name **`bot-network`** must be
  updated to **`bot-net`**.
- If you relied on qdrant being exposed on localhost:6333 you must
  publish that port manually.

## [0.3.3] – 2025-07-18

### Fixed
- **First-run migrations**  
  Fresh deployments no longer crash with *“relation content does not exist”* –  
  the initial Alembic revision now creates the `content` table and index in one
  pure-SQL block, instead of attempting to alter a non-existent table.

### Changed
- **Docker Compose**
  - Postgres is mapped to host&nbsp;`9441:5432`; Qdrant is mapped to
    `6333:6333` for local inspection.
  - Minor comment/formatting tweaks in the `migrator` service stanza.

- **Google Doc loader**
  - Added debug logs that print whether the Qdrant collection is empty and how
    many vectors will be (re)embedded – helps trace cold-start ingestion.

### Notes
Deployments created **from scratch** (`docker compose up -d --build`) now run
cleanly: the *migrator* container exits 0, Qdrant and the bot start without
manual intervention.

## [0.3.4] – 2025-07-20

### Fixed
- **Message formatting**  
  `remove_seo_hashtags()` no longer strips hard line breaks, so bullet lists
  copied from Google Docs render correctly in Telegram (HTML parse_mode)

### Changed
- Added verbose debug statements in `user_router.py` (`cb_open`) and
  `google_doc_loader.py` (collection count) to simplify production trouble-
  shooting — follows best-practice advice for human-oriented changelogs

## [0.3.5] – 2025-07-20

### Fixed
- **Google-Docs parser** now recognises indented heading markers (`H1:`‒`H4:`) and keeps blank lines as deliberate breaks, so long articles retain structure in Telegram.  
- **Paragraph extraction** preserves trailing whitespace, preventing accidental loss of inline formatting coming from Google Docs.  
- **Inline-keyboard labels** are cleaned with a stricter regex that removes HTML tags without stripping entities, eliminating broken button text.  
- **Search snippets** no longer double-strip SEO hashtags and stay within Telegram’s limits while keeping HTML balanced, stopping layout glitches in answers.

## [0.3.6] – 2025-07-20

### Fixed
- **Cold-start vector loss** – the bot now detects an empty **Qdrant** collection and re-embeds *all* content nodes on boot, so search works after a fresh deploy.  
- **Unbalanced heading HTML** – Google Docs headings are saved as plain text; stray `<b>` tags can no longer leak into `content.title`, preventing broken breadcrumbs & buttons.  
- **Inline-keyboard titles** – stricter tag-stripping (`<[^>]+>`) plus `html.unescape()` keeps button labels human-readable.  
- **Search snippets** – blank articles no longer generate double line-breaks; welcome copy updated for clarity.

### Changed
- **GoogleDocLoader** refactored: unified “needs re-embed” logic via `force_reembed_all`, deduplicating `embed_candidates`.  
- Internal logging improved for collection state & embedding stats.

### Notes
These fixes close the regression introduced in *v0.3.5* that left Qdrant empty after container rebuilds.

## [0.3.7] – 2025-07-20

### Performance
- **Qdrant collection preservation**  
  `ensure_collection()` now checks an existing collection’s
  `size` & `distance` and keeps it when they match the embedding model.
  Startup re-embeds **only modified nodes**, not the whole corpus, cutting
  cold-start time and CPU usage.

### Tooling
- **LLM helper update**  
  `tools/dcl.ps1` tweaks the “commit_message” task so generated messages
  start with the new semantic version, streamlining release automation.

### Internal
- Added compatibility shim for both old (`VectorParams`) and new
  (`dict[str, VectorParams]`) collection layouts returned by
  `get_collection()`.

No database schema or API changes.

## [0.4.0] – 2025-07-20

### Added
- **`src/tools` package** – new home for shared utilities (`db.py`, `embeddings.py`,
  `logger.py`, `qdrant_high_level_client.py`, `utils_*`, plus `__init__.py`).

### Changed
- **Project structure refactor**
  - All helpers formerly under `src.bot.*` moved to `src.tools.*`; every import
    across the code-base updated accordingly.
  - Main entry point relocated to `src/main.py`; **Dockerfile** `CMD` now
    `uv run -m src.main`, still leveraging BuildKit’s `COPY --link` optimisation
    for fast builds.
  - `config.py` now resolves `project_root_path` relative to the new layout.
  - Alembic `env.py`, Google Docs loader, search service, and tests point to the
    new module paths, following best practice for explicit imports in Alembic
    environments.
  - Updated Testcontainers fixture to import the relocated pool initialiser.
  - Logger path configuration adjusted after the move and still uses Loguru
    idioms.
  - Docker image still installs dependencies with **uv** (validated against
    current uv docs).

### Fixed
- Incorrect `project_root_path` that pointed one level too high after the
  directory shuffle caused mis-resolved log paths.

### Breaking
- **Import paths** – replace `src.bot.*` with `src.tools.*` in any external code
  or third-party integrations.
- **Docker CMD / scripts** – update references from `src.bot.main` to `src.main`.

### Notes
No database-schema changes. Runtime behaviour is identical once paths
are updated. The refactor aligns module layout with Python packaging
recommendations for maintainability.

## [0.4.1] – 2025‑07‑27

### Added
- **bot‑navigation:** `build_children_kb` now accepts a `main_menu: bool` flag to suppress the “⬅️ Назад” button on the main menu.  
- Updated `user_router.py`:
  - `cmd_help` and `cb_home` pass `main_menu=True`.
  - Added logging to `cb_open` and `cb_back` for better debug insight.
  - Improved `cb_open` fallback logic to avoid `None` in callback_data.

## [0.4.2] - 2025-08-19

### Added
- **bot-navigation:** `build_children_kb` now accepts `current_id` and `previous_menu_message_id` parameters in order to display new button "💾 Сохранить информацию в чате"
- Updated `user_router.py`:
  - minor changes in `cb_open` - now passing `current_id` - current content id and `previous_menu_message_id` latest active menu message id to `build_children_kb`
  - new handler `cb_save` - processes presses on new button "💾 Сохранить информацию в чате" - sends plain text to user, deletes old menu (because it is now not the latest message), sends new menu

## [0.5.0] – 2025-08-23

### Added
- **Runtime logging**  
  - Enabled `UserActionsLogMiddleware` (incoming updates) and `OutgoingLoggingMiddleware` (Bot API deliveries) in `main.py`, providing per-event activity rows and message-delivery tracking for observability and analytics.

### Changed
- **Alembic**: timestamped revision filenames via `file_template` in `alembic.ini` (clean history & easier auditing).  
- **Dockerfile**: removed `ENTRYPOINT` wrapper; container now starts directly via `CMD`.  
- **Repo hygiene**: ignore `*.xml` files.  
- **Migrations template**: dropped unused `sqlalchemy` import from `migrations/script.py.mako`.  
- **User router**: minor whitespace/formatting only.

> Notes: Version bumped as a MINOR under SemVer (pre-1.0) for a new feature, and entries grouped per *Keep a Changelog* conventions.

## [0.6.0] – 2025-08-24

### Added
- **Content Sync package** (`src/content_sync/`) to separate concerns and keep the ingestion/search path maintainable:
  - `sources/google_docs.py` – Google Docs fetch + HTML normalization
  - `parsing/parser.py` – H1–H4 → tree parsing (existing rules preserved)
  - `storage/repository.py` – KV revision helpers and `(parent_id, ord)` upsert logic
  - `vectorstore/qdrant_store.py` – robust Qdrant emptiness check (`scroll(1)` with `count()` fallback), upsert/delete
  - `models.py` – `ContentNode`, `SyncStats`
  - `pipeline/sync.py` – `run_once()` orchestrator for the full sync (fetch → revision check → parse → DB upserts/moves → delete missing → embed + upsert)

### Changed
- **Startup flow:** `main.py` now calls `run_once(force_reembed_all_if_empty=True)` after `ensure_collection()`.
- **Vector ingestion:** embedding + upsert happens via the pipeline; behavior is unchanged but code is now modular.

### Deprecated
- `src/tools/google_doc_loader.py` is no longer used and will be removed in a future release.

### Removed
- `src/tools/google_doc_loader.py`

> Notes: Internal refactor only: **no database schema changes** and no user-visible behavior changes.

## [0.6.2] – 2025-08-24

### Added
- **Renderer module**: `src/bot/renderers/content_renderer.py` centralizes:
  - Breadcrumb building (`build_breadcrumb_text`)
  - HTML sanitizing + SEO hashtag cleanup
  - Telegram-safe chunking with balanced-HTML fallback (`render_leaf_message`)

### Changed
- **User router**: `cb_open` and `cb_save` now delegate rendering to the new module, removing ~70 lines of duplicated logic while preserving output.

### Fixed
- Removed fragile `escape` import from utils (now uses `html.escape` in renderer).
- Avoided string placeholders for `parent_id`; guarded `None` in `cb_back`.

> Notes: Internal refactor only — no schema or user-visible behavior changes.

## [0.6.3] – 2025-08-24

### Changed
- **Content Sync:** consolidated Google Docs loader — `src/content_sync/sources/google_docs.py` is now the canonical implementation.
- **Code hygiene:** removed an unused import from `src/content_sync/models.py`.

### Deprecated
- `src/content_sync/google_docs.py` removed.

## \[0.6.4] – 2025-08-24

### Changed

* **Content domain consolidation**: migrated `src/content_sync/*` into `src/content/*` and exposed public APIs via `src/content/__init__.py`.
* **Imports rewired**: `user_router.py`, `keyboard.py`, tests, and the sync pipeline now import from `src.content.*`.
* **Pipeline & runtime**: `main.py` imports `run_once` from `src.content.sync.pipeline.sync`; removed an unused `ensure_collection` import in the Qdrant store.

### Fixed

* **KV revision write**: `set_doc_revision()` now performs an UPSERT, preventing failures when the `doc_revision` key doesn’t exist on first run.

> Notes: No database schema changes. No user-visible behavior changes.
