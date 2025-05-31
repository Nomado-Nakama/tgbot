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
