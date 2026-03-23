# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```
spotme/
├── server/                    # Python FastAPI backend
│   ├── main.py                # App factory, middleware, router registration, inline migrations
│   ├── config.py              # Settings (pydantic-settings), timezone, today_eastern()
│   ├── database.py            # SQLAlchemy engine, session factory, per-user DB routing
│   ├── models.py              # 13 SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic request/response DTOs
│   ├── utils.py               # recovery_zone() helper
│   ├── cli.py                 # CLI entry point for background jobs (whoop_sync)
│   ├── routes/                # FastAPI routers (11 files)
│   │   ├── chat.py            # POST /chat, GET /chat/history, /chat/days, /chat/day
│   │   ├── workout.py         # Workout CRUD, set logging, completion
│   │   ├── program.py         # GET /program, /program/week/{n}
│   │   ├── progress.py        # GET /progress, /progress/prs
│   │   ├── meals.py           # Meal CRUD, daily/weekly totals
│   │   ├── morning.py         # GET /morning briefing
│   │   ├── profile.py         # GET/POST /profile
│   │   ├── whoop.py           # Whoop login, sync, status, retry
│   │   ├── interview.py       # POST /interview/questions
│   │   ├── video.py           # POST /video (form check upload + analysis)
│   │   └── layout.py          # GET /layout (Claude-generated layouts)
│   ├── services/              # Business logic (7 files)
│   │   ├── claude_service.py  # ClaudeService, assemble_context(), _call_claude(), tool loop
│   │   ├── whoop_service.py   # Biometric sync, workout push, journal sync, queue processing
│   │   ├── whoop_tools.py     # Tool handler dispatch for Claude's tool_calls
│   │   ├── workout_sequencer.py # Set-by-set workout management
│   │   ├── program_parser.py  # Markdown program parsing into structured weeks/days
│   │   ├── layout_service.py  # Layout validation (component type whitelist)
│   │   ├── video_service.py   # FFmpeg frame extraction
│   │   └── notification_service.py # ntfy.sh push notifications
│   └── scripts/               # Standalone scripts for systemd timers
│       └── morning_briefing.py # HTTP client that hits /api/whoop/sync then /api/morning
├── frontend/                  # React 19 + TypeScript PWA
│   ├── src/
│   │   ├── main.tsx           # React DOM render entry
│   │   ├── App.tsx            # Root component: onboarding gate, 4-tab nav
│   │   ├── api.ts             # All API calls (typed fetch wrapper)
│   │   ├── db.ts              # IndexedDB for offline sets and cached layouts
│   │   ├── types.ts           # TypeScript interfaces (ChatResponse, PlannedSet, etc.)
│   │   ├── index.css          # Global styles
│   │   ├── screens/           # Full-page views (10 files)
│   │   │   ├── workout.tsx    # Primary chat + workout screen (state A/B/C pattern)
│   │   │   ├── workout-home.tsx # Day list for browsing chat history
│   │   │   ├── workout-session.tsx # Layout-driven workout session
│   │   │   ├── coach.tsx      # Standalone chat (legacy/alternate)
│   │   │   ├── dashboard.tsx  # Layout-driven dashboard with offline fallback
│   │   │   ├── history.tsx    # Workout history + program tabs
│   │   │   ├── diet.tsx       # Meal tracking and nutrition view
│   │   │   ├── profile.tsx    # User profile + Whoop settings
│   │   │   ├── program.tsx    # Program week view
│   │   │   └── progress.tsx   # Charts (e1RM, volume, Whoop trends)
│   │   ├── components/        # Reusable UI components (26 files)
│   │   │   ├── layout-renderer.tsx  # Maps Claude's layout JSON to React components
│   │   │   ├── chat-bubble.tsx      # Message display
│   │   │   ├── set-card.tsx         # Active set tracking card
│   │   │   ├── exercise-card.tsx    # Exercise display
│   │   │   ├── context-banner.tsx   # Date/workout context display
│   │   │   ├── recovery-banner.tsx  # Whoop recovery zone display
│   │   │   ├── program-view.tsx     # Full program display
│   │   │   ├── program-week.tsx     # Week-level program view
│   │   │   ├── program-day.tsx      # Day-level program view
│   │   │   ├── day-card.tsx         # Day summary card
│   │   │   ├── onboarding.tsx       # Onboarding flow wrapper
│   │   │   ├── coach-interview.tsx  # Multi-step interview component
│   │   │   ├── intake.tsx           # Initial profile intake form
│   │   │   ├── bottom-nav.tsx       # Tab navigation bar
│   │   │   ├── header.tsx           # Layout component: header
│   │   │   ├── stat-card.tsx        # Layout component: stat card
│   │   │   ├── set-logger.tsx       # Layout component: set logger
│   │   │   ├── rest-timer.tsx       # Layout component: rest timer
│   │   │   ├── text-block.tsx       # Layout component: text block
│   │   │   ├── action-button.tsx    # Layout component: action button
│   │   │   ├── video-prompt.tsx     # Layout component: video prompt
│   │   │   ├── chart.tsx            # Layout component: chart
│   │   │   ├── mini-chart.tsx       # Small inline chart
│   │   │   ├── nutrition-card.tsx   # Nutrition summary card
│   │   │   ├── meal-card.tsx        # Individual meal display
│   │   │   ├── workout-bar.tsx      # Workout progress bar
│   │   │   ├── workout-detail.tsx   # Expanded workout view
│   │   │   └── prs-tab.tsx          # Personal records tab
│   │   └── hooks/             # Custom React hooks (3 files)
│   │       ├── use-offline.ts # Online/offline detection + sync
│   │       ├── use-voice.ts   # SpeechRecognition wrapper
│   │       └── use-camera.ts  # Camera access (for video form checks)
│   └── dist/                  # Built PWA (served by FastAPI in production)
├── tests/                     # pytest suite (18 test files)
│   ├── test_chat.py
│   ├── test_workout.py
│   ├── test_program.py
│   ├── test_program_week.py
│   ├── test_meals.py
│   ├── test_meals_day.py
│   ├── test_morning.py
│   ├── test_progress.py
│   ├── test_history_prs.py
│   ├── test_layout.py
│   ├── test_video.py
│   ├── test_whoop.py
│   ├── test_whoop_tools.py
│   ├── test_claude_sdk.py
│   ├── test_database.py
│   ├── test_sequencer.py
│   ├── test_complete_set.py
│   ├── test_training_log.py
│   ├── test_daily_chat.py
│   └── test_utils.py
├── alembic/                   # Database migrations
│   ├── env.py
│   └── versions/
│       ├── fa1934893c73_add_training_log_table.py
│       └── 002_whoop_v04.py
├── deploy/                    # systemd service/timer files
│   ├── spotme.service         # Main uvicorn server
│   ├── spotme-morning.service # Morning briefing oneshot
│   ├── spotme-morning.timer   # Triggers at 07:00
│   ├── spotme-whoop-sync.service
│   └── spotme-whoop-sync.timer # Every 4 hours
├── docs/                      # Design docs and specs
├── pyproject.toml             # Python project config, dependencies
├── alembic.ini                # Alembic config
├── CLAUDE.md                  # Project-level AI instructions
└── .planning/                 # GSD planning artifacts
    └── codebase/              # This analysis
```

## Directory Purposes

**`server/routes/`:**
- Purpose: HTTP endpoint handlers, request orchestration, side-effect processing
- Contains: 11 FastAPI `APIRouter` modules, one per domain
- Key files: `chat.py` is the most complex (~450 lines, handles all Claude response side effects), `workout.py` handles set CRUD and workout lifecycle
- Pattern: Each file exports `router = APIRouter()`, registered in `server/main.py` with `/api` prefix

**`server/services/`:**
- Purpose: Business logic isolated from HTTP concerns
- Contains: 7 service modules plus `__init__.py`
- Key files: `claude_service.py` (Claude CLI integration, context assembly, tool loop), `whoop_service.py` (biometric sync, workout push, journal sync), `workout_sequencer.py` (set-by-set flow management)
- Pattern: Mix of classes (`ClaudeService`, `VideoService`) and free functions. Services are stateless, instantiated per-request.

**`frontend/src/screens/`:**
- Purpose: Full-page views corresponding to app tabs/states
- Contains: 10 screen components
- Key files: `workout.tsx` is the primary user-facing screen (chat + workout combined, ~200 lines with 3 internal states: daily chat, day list, active workout)

**`frontend/src/components/`:**
- Purpose: Reusable UI primitives and layout components
- Contains: 26 component files
- Key files: `layout-renderer.tsx` (maps Claude's JSON layout descriptors to React components), `set-card.tsx` (active workout set tracking), `onboarding.tsx` (initial setup flow)

**`frontend/src/hooks/`:**
- Purpose: Shared React hooks for device capabilities
- Contains: 3 hooks (offline sync, voice input, camera)

**`tests/`:**
- Purpose: pytest test suite for backend
- Contains: 18 test files, no frontend tests
- Pattern: Tests use `sqlite:///:memory:` with `StaticPool`, mock Claude via monkeypatch

**`deploy/`:**
- Purpose: systemd service and timer definitions for Steam Deck deployment
- Contains: 5 files (1 main service, 2 service+timer pairs for morning briefing and whoop sync)

**`alembic/`:**
- Purpose: Database migration scripts
- Contains: Migration runner config and 2 version files
- Note: Most schema evolution happens via inline ALTER TABLE in `server/main.py::create_app()`, not via Alembic migrations

## Key File Locations

**Entry Points:**
- `server/main.py`: FastAPI app factory and server entry (`app = create_app()`)
- `frontend/src/main.tsx`: React DOM render
- `frontend/src/App.tsx`: Root component (onboarding gate + tab router)
- `server/cli.py`: CLI for background jobs
- `server/scripts/morning_briefing.py`: Scheduled morning push

**Configuration:**
- `server/config.py`: `Settings` class (loads `.env`), `today_eastern()`, `TIMEZONE`
- `pyproject.toml`: Python dependencies, build config, pytest config
- `frontend/vite.config.ts`: Vite build config (not in source tree but referenced)
- `alembic.ini`: Alembic migration config
- `CLAUDE.md`: Project-level AI instructions (root)
- `server/CLAUDE.md`: Backend-specific AI instructions

**Core Logic:**
- `server/services/claude_service.py`: Claude CLI invocation, context assembly, tool-use loop
- `server/routes/chat.py`: Primary chat endpoint with all side-effect processing
- `server/services/whoop_service.py`: Whoop API integration
- `server/services/workout_sequencer.py`: Set-by-set workout management
- `server/services/program_parser.py`: Training program markdown parser

**Data Layer:**
- `server/models.py`: All 13 SQLAlchemy models
- `server/database.py`: Engine, sessions, per-user DB routing
- `server/schemas.py`: Pydantic DTOs

**Testing:**
- `tests/test_chat.py`: Chat endpoint tests
- `tests/test_sequencer.py`: Workout sequencer unit tests
- `tests/test_training_log.py`: Training log feature tests

## Naming Conventions

**Files:**
- Python: snake_case (`claude_service.py`, `whoop_tools.py`)
- TypeScript: kebab-case (`layout-renderer.tsx`, `use-offline.ts`)
- Test files: `test_{module}.py` in `tests/` directory

**Directories:**
- All lowercase, no separators (`routes`, `services`, `components`, `screens`, `hooks`)

**Python modules:**
- Route files export `router = APIRouter()`
- Service files export classes or free functions
- Models file contains all ORM classes in one file

**React components:**
- One component per file
- PascalCase exports (`LayoutRenderer`, `ChatBubble`, `SetCard`)
- kebab-case filenames matching component (`layout-renderer.tsx` -> `LayoutRenderer`)

**API constants:**
- `MEMORY_KEY = "training_plan"` in `server/routes/chat.py`
- `CLAUDE_BIN`, `MODEL`, `SYSTEM_PROMPT`, `WHOOP_TOOLS`, `MAX_TOOL_ITERATIONS` in `server/services/claude_service.py`
- `VALID_COMPONENT_TYPES` in `server/services/layout_service.py`

## Where to Add New Code

**New API Endpoint:**
1. Create `server/routes/new_route.py` with `router = APIRouter()`
2. Add request/response schemas to `server/schemas.py`
3. Register in `server/main.py`: `app.include_router(router, prefix="/api")`
4. Add tests in `tests/test_new_route.py`
5. Add API method in `frontend/src/api.ts`

**New Service/Business Logic:**
- Create `server/services/new_service.py`
- Import and use from route handlers
- Keep services stateless -- instantiate per-request or use free functions

**New Claude Tool (Whoop):**
1. Add tool schema dict to `WHOOP_TOOLS` list in `server/services/claude_service.py`
2. Add async handler function in `server/services/whoop_tools.py`
3. Register in `TOOL_HANDLERS` dict in `server/services/whoop_tools.py`

**New Layout Component:**
1. Create `frontend/src/components/new-component.tsx`
2. Add to `COMPONENT_MAP` in `frontend/src/components/layout-renderer.tsx`
3. Add type string to `VALID_COMPONENT_TYPES` in `server/services/layout_service.py`
4. Add to `ComponentType` union in `frontend/src/types.ts`

**New Frontend Screen:**
1. Create `frontend/src/screens/new-screen.tsx`
2. Add to tab routing in `frontend/src/App.tsx`
3. Add tab to `BottomNav` in `frontend/src/components/bottom-nav.tsx`

**New React Hook:**
- Create `frontend/src/hooks/use-new-hook.ts`
- Export camelCase function (`useNewHook`)

**New Database Table:**
1. Add model class to `server/models.py`
2. Add Alembic migration in `alembic/versions/` (or use inline ALTER TABLE in `server/main.py` for simple additions)
3. `Base.metadata.create_all()` in `server/main.py::create_app()` handles initial creation

**New Context Source for Claude:**
- Add parameter to `assemble_context()` in `server/services/claude_service.py`
- Add data gathering in `server/routes/chat.py::chat()` handler
- Append formatted text to `parts` list in `assemble_context()`

**New Claude Response Field (side effect):**
1. Add field to `SYSTEM_PROMPT` JSON format documentation in `server/services/claude_service.py`
2. Extract from `result` dict in `ClaudeService.chat()` return value
3. Handle side effect in `server/routes/chat.py::chat()` after the Claude call
4. Add to `ChatResponse` schema if it needs to reach the frontend

## Special Directories

**`.planning/`:**
- Purpose: GSD planning and analysis artifacts
- Generated: Yes (by Claude Code)
- Committed: No (typically gitignored)

**`frontend/dist/`:**
- Purpose: Built PWA static files
- Generated: Yes (`npm run build`)
- Committed: No (gitignored)
- Served: By FastAPI in production via `StaticFiles` mount

**`deploy/`:**
- Purpose: systemd unit files for Steam Deck deployment
- Generated: No
- Committed: Yes

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No

**`docs/superpowers/`:**
- Purpose: Design specs and plans from AI-assisted planning sessions
- Generated: Yes
- Committed: Yes

---

*Structure analysis: 2026-03-23*
