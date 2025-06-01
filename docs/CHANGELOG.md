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
