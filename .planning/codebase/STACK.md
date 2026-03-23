# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.11+ - Backend API, business logic, CLI tools (`server/`, `tests/`)
- TypeScript ~5.9.3 - Frontend PWA (`frontend/src/`)

**Secondary:**
- SQL (SQLite dialect) - Database queries, migrations (`alembic/`)
- Bash - systemd service files, deploy scripts (`deploy/`)

## Runtime

**Environment:**
- Python 3.11+ (production runs in `.venv` at `~/spotme/.venv/bin/`)
- Node.js 20 (build-time only for frontend; Docker uses `node:20-slim`)
- Claude Code CLI 2.1.81 installed at `/home/deck/.local/bin/claude` (symlink to `/home/deck/.local/share/claude/versions/2.1.81`)

**Package Manager:**
- pip with hatchling build backend (`pyproject.toml`)
- npm with lockfile (`frontend/package-lock.json`)
- Lockfile: present for frontend, not used for Python (no `requirements.txt` or `pip.lock`)

## Frameworks

**Core:**
- FastAPI >=0.110 - HTTP API server (`server/main.py`)
- React 19.2.4 - Frontend UI (`frontend/src/`)
- SQLAlchemy 2.0+ - ORM and database access (`server/models.py`, `server/database.py`)

**Testing:**
- pytest >=8.0 - Test runner (`tests/`)
- pytest-asyncio >=0.23 - Async test support (mode: `auto`)
- httpx >=0.27 - HTTP client for route testing

**Build/Dev:**
- Vite 8.0 - Frontend bundler and dev server (`frontend/vite.config.ts`)
- vite-plugin-pwa 1.2.0 - Service worker and PWA manifest generation
- Workbox 7.4.0 - Runtime caching in service worker
- ruff >=0.3 - Python linting
- ESLint 9 + typescript-eslint - TypeScript linting (`frontend/eslint.config.js`)

## Key Dependencies

**Critical:**
- `claude` CLI binary (2.1.81) - All AI inference runs through `claude --print` subprocess, NOT the Anthropic Python SDK. The `anthropic>=0.40` pip dependency exists in `pyproject.toml` but is NOT used for API calls. See INTEGRATIONS.md for full details.
- `fastapi>=0.110` - HTTP framework (`server/main.py`)
- `sqlalchemy>=2.0` - All database access (`server/database.py`, `server/models.py`)
- `pydantic-settings>=2.0` - Config loading from `.env` (`server/config.py`)

**Infrastructure:**
- `uvicorn>=0.27` - ASGI server (`deploy/spotme.service`)
- `alembic>=1.13` - Database migrations (`alembic/`, `alembic.ini`)
- `httpx` - Used for ntfy.sh notifications (`server/services/notification_service.py`) and morning briefing script (`server/scripts/morning_briefing.py`)
- `python-multipart>=0.0.9` - File upload handling for video analysis (`server/routes/video.py`)
- `python-dotenv>=1.0` - `.env` file loading

**Optional:**
- `whoop-write-api` - Reverse-engineered Whoop integration, installed from git (`git+https://github.com/jd1207/whoop-write-api.git`). Optional dependency group: `pip install -e ".[whoop]"`. Always lazy-imported inside functions, never at module top level.

**Frontend:**
- `react` 19.2.4, `react-dom` 19.2.4 - UI rendering
- `workbox-window` 7.4.0 - Service worker registration
- `@vitejs/plugin-react` 6.0 - React Fast Refresh for Vite

## Configuration

**Environment:**
- Config loaded via `pydantic_settings.BaseSettings` in `server/config.py`
- `.env` file at project root (existence confirmed; contents not read)
- `.env.example` declares: `DATABASE_URL`, `VIDEO_DIR`
- `anthropic_api_key` field exists in Settings but is unused by the main chat flow (Claude CLI uses OAuth instead)
- `ntfy_topic` - Push notification topic for ntfy.sh
- Timezone hardcoded: `America/New_York` in `server/config.py`

**Build:**
- `pyproject.toml` - Python package config with hatchling backend
- `frontend/vite.config.ts` - Vite + PWA plugin config
- `frontend/tsconfig.app.json` - TypeScript strict mode, ES2023 target, `verbatimModuleSyntax: true`
- `alembic.ini` - Migration config pointing to `alembic/` directory

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 20+ (for frontend build)
- Claude Code CLI installed and authenticated via OAuth
- ffmpeg (runtime dependency for video frame extraction)
- SQLite 3.x (ships with Python)

**Production (Steam Deck):**
- Arch Linux-based, read-only rootfs
- All installs to `~/.local/bin`
- Runs as systemd user service (not root): `deploy/spotme.service`
- Accessible via Tailscale (no app-level auth)
- uvicorn bound to `127.0.0.1:8000`
- Claude CLI at `/home/deck/.local/bin/claude`
- PATH must include `~/.local/bin` for Claude CLI access

**Docker (alternative):**
- Multi-stage build: `node:20-slim` for frontend, `python:3.12-slim` for backend
- Claude Code CLI installed in container via curl or npm
- Claude credentials mounted read-only: `~/.claude:/root/.claude:ro`
- Persistent data volume at `/data/spotme.db`
- Exposed on port 8000

## Scheduled Jobs

**systemd timers (deploy/):**
- `spotme-whoop-sync.timer` - Whoop biometric sync every 4 hours (`00,04,08,12,16,20:00`)
- `spotme-morning.timer` - Morning briefing with push notification at 07:00 daily

---

*Stack analysis: 2026-03-23*
