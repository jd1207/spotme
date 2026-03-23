# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Monolithic client-server with AI-mediated command pattern

**Key Characteristics:**
- Single FastAPI server serves both the REST API and the built PWA static files
- Claude acts as a "universal controller" -- user messages go to Claude, Claude's JSON response drives all side effects (profile updates, meal logging, memory writes, workout creation, Whoop tool calls)
- Claude is invoked via CLI subprocess (`claude --print`), inheriting OAuth session from the host machine -- NOT via the Anthropic SDK directly
- Context assembly is the central architectural concept: every chat request builds a text context string from ~8 data sources and injects it as system prompt appendix
- SQLite with WAL mode is the sole data store; no caching layer, no message queue

## Layers

**Frontend (PWA):**
- Purpose: Chat UI, workout tracking UI, offline set logging, layout rendering
- Location: `frontend/src/`
- Contains: React 19 + TypeScript components and screens
- Depends on: Backend REST API via `frontend/src/api.ts`
- Used by: User's phone browser

**API Routes:**
- Purpose: HTTP endpoints, request validation, response shaping, side-effect orchestration
- Location: `server/routes/`
- Contains: 11 FastAPI routers (chat, workout, video, profile, whoop, progress, layout, morning, program, meals, interview)
- Depends on: Services layer, Models, Database
- Used by: Frontend via `/api` prefix

**Services:**
- Purpose: Business logic, external integrations, data transformation
- Location: `server/services/`
- Contains: ClaudeService, whoop_service, whoop_tools, layout_service, video_service, notification_service, workout_sequencer, program_parser
- Depends on: Claude CLI, Whoop API, ffmpeg, ntfy.sh
- Used by: Route handlers

**Models:**
- Purpose: ORM definitions, database schema
- Location: `server/models.py`
- Contains: 13 SQLAlchemy models (Program, Workout, Exercise, Set, WhoopData, FormCheck, Conversation, UserProfile, SystemMemory, WhoopToken, WhoopSyncQueue, Meal, ExerciseCatalog, TrainingLog)
- Depends on: SQLAlchemy Base from `server/database.py`
- Used by: All routes and services

**Database:**
- Purpose: Connection management, session factory, per-user DB routing
- Location: `server/database.py`
- Contains: Engine creation, WAL pragma setup, `get_db()` dependency, multi-user context var routing
- Depends on: SQLite, `server/config.py`
- Used by: All routes via `Depends(get_db)`

**Configuration:**
- Purpose: Environment loading, timezone, date utilities
- Location: `server/config.py`
- Contains: `Settings` (pydantic-settings), `today_eastern()`, `TIMEZONE`
- Depends on: `.env` file
- Used by: Everything

## Data Flow

**Primary Chat Flow (PWA -> Claude -> Side Effects):**

1. User types message in `frontend/src/screens/workout.tsx`, calls `api.chat(text, workoutId, date)`
2. `POST /api/chat` hits `server/routes/chat.py::chat()`
3. Route handler gathers 8+ data sources in parallel:
   - `UserProfile` from DB
   - `WhoopData` for today (triggers background sync if missing)
   - Last 15 completed sets across recent workouts
   - Last 10 `Conversation` rows for this date
   - Active workout context (exercises + set completion counts)
   - `SystemMemory` row with key `"training_plan"` (the training program)
   - Today's meal totals (sum of calories/protein/carbs/fat)
   - Last 15 `TrainingLog` entries (completions, notes, adjustments)
4. `assemble_context()` in `server/services/claude_service.py` concatenates all sources into a single text string
5. `ClaudeService.chat()` checks if Whoop is connected:
   - **Without Whoop:** calls `_call_claude(system, message)` -- single subprocess
   - **With Whoop:** calls `_call_claude_with_tools()` -- up to 3 iterative subprocesses with tool descriptions embedded in system prompt
6. `_call_claude()` spawns `claude --print --model claude-sonnet-4-20250514 --append-system-prompt <system> -p <message>` as async subprocess, waits up to 120s
7. Raw stdout is parsed: `_extract_json()` strips code fences and finds JSON object
8. Response JSON is parsed for side-effect fields: `profile`, `memory_update`, `training_log_entry`, `meal`, `workout_plan`, `set_suggestion`, `layout`
9. Route handler processes each side-effect:
   - `profile` -> upsert `UserProfile`
   - `memory_update` -> upsert `SystemMemory(key="training_plan")` (blocked if `training_log_entry` present)
   - `training_log_entry` -> append to `TrainingLog` table
   - `meal` -> insert `Meal` + trigger Whoop journal sync
   - `workout_plan` -> `create_workout_from_plan()` creates `Workout`/`Exercise`/`Set` rows
   - `layout` -> validated by `validate_layout()` (whitelist of 10 component types)
10. User + assistant messages saved to `Conversation` table with date scope
11. Response returned: `{response, layout, set_suggestion, workout_active, current_set, workout_id}`

**Tool-Use Flow (Claude -> Whoop):**

1. `_call_claude_with_tools()` appends tool descriptions to system prompt as markdown
2. Claude is asked to include `"tool_calls"` array in its JSON response
3. If tool_calls present, each is dispatched to `execute_whoop_tool()` in `server/services/whoop_tools.py`
4. Tool handler map (`TOOL_HANDLERS`) routes to specific async functions (e.g., `handle_create_activity`)
5. Each handler lazy-imports `get_whoop_client(db)` and calls Whoop API
6. Results collected into `tool_results_summary` list
7. Follow-up Claude subprocess spawned with tool results as message
8. Loop repeats up to `MAX_TOOL_ITERATIONS = 3` times, or until no more tool_calls

**State Management:**
- Server-side only. No client-side state persistence except IndexedDB for offline sets and cached layouts
- Conversation history scoped by date (not session ID) via `Conversation.date` column
- Training program stored as raw markdown in `SystemMemory(key="training_plan")`
- Training log is append-only (`TrainingLog` table)
- Frontend maintains ephemeral React state; rehydrates from server on tab visibility change

## Key Abstractions

**ClaudeService:**
- Purpose: Wraps all Claude CLI interactions
- File: `server/services/claude_service.py`
- Pattern: Stateless service class instantiated per-request (`ClaudeService()`)
- Methods: `chat()`, `generate_interview_questions()`, `analyze_form()`

**assemble_context():**
- Purpose: Build the complete context string from all data sources
- File: `server/services/claude_service.py` (lines 187-293)
- Pattern: Free function, takes 11 parameters, returns concatenated string
- Critical: This is the primary mechanism for giving Claude knowledge about the user. Every piece of data Claude sees flows through here.

**SystemMemory:**
- Purpose: Key-value store for persistent AI state
- File: `server/models.py` (line 101)
- Pattern: Single-row per key. Key `"training_plan"` holds the full training program as markdown. Other keys used for onboarding flags (`whoop_first_workout_shown`, `whoop_journal_education_shown`, `whoop_status`)

**TrainingLog:**
- Purpose: Append-only log of training events (completions, notes, adjustments)
- File: `server/models.py` (line 155)
- Pattern: Separated from SystemMemory to prevent Claude from accidentally overwriting the training program when logging a workout completion

**workout_sequencer:**
- Purpose: Manages the set-by-set workout flow
- File: `server/services/workout_sequencer.py`
- Pattern: Creates Workout/Exercise/Set records from Claude's `workout_plan` array, tracks set completion order, provides `get_next_set()` for the UI

## Entry Points

**FastAPI Server:**
- Location: `server/main.py` (line 140: `app = create_app()`)
- Triggers: `uvicorn server.main:app --host 127.0.0.1 --port 8000`
- Responsibilities: Registers all 11 routers under `/api`, serves frontend static files, runs startup migrations (inline ALTER TABLE for schema evolution)

**Morning Briefing Script:**
- Location: `server/scripts/morning_briefing.py`
- Triggers: systemd timer at 07:00 daily (`deploy/spotme-morning.timer`)
- Responsibilities: Calls `/api/whoop/sync` then `/api/morning?notify=true` to push morning notification

**CLI Entry Point:**
- Location: `server/cli.py`
- Triggers: `python -m server.cli whoop_sync`
- Responsibilities: Background whoop sync with dedup (3-hour window) and auth failure tracking

**Frontend SPA:**
- Location: `frontend/src/main.tsx` -> `frontend/src/App.tsx`
- Triggers: Browser navigation to server root
- Responsibilities: Renders Onboarding or 4-tab app (workout/program/diet/profile)

## Error Handling

**Strategy:** Defensive with graceful degradation. Every external call wrapped in try/except.

**Patterns:**
- Claude CLI failure: Returns hardcoded fallback response `"Having trouble reaching Claude right now. Try again in a sec."` (`server/services/claude_service.py` line 317)
- Claude JSON parse failure: Returns raw text as response with all optional fields null (`server/services/claude_service.py` line 321)
- Whoop API failure: Queues to `WhoopSyncQueue` table for retry (max 3 retries), app continues without Whoop data (`server/services/whoop_service.py` line 173)
- Whoop tool failure: Returns `{"error": str(e)}` to Claude for graceful response (`server/services/whoop_tools.py` line 89-90)
- Invalid layout from Claude: Falls back to `None` layout, frontend renders text-only (`server/services/layout_service.py`)
- Frontend offline: IndexedDB queues sets for sync on reconnect (`frontend/src/hooks/use-offline.ts`)

## Cross-Cutting Concerns

**Logging:**
- Python stdlib `logging` module used throughout
- Logger per module: `logger = logging.getLogger(__name__)`
- No structured logging, no log aggregation
- CLI configures basic format: `%(asctime)s %(name)s %(message)s`

**Validation:**
- Request validation via Pydantic schemas in `server/schemas.py`
- Layout validation via whitelist in `server/services/layout_service.py`
- No validation of Claude's side-effect fields (profile, meal, etc.) beyond `isinstance` checks
- No input sanitization for SQL (SQLAlchemy ORM handles parameterization)

**Authentication:**
- No app-level auth. Tailscale VPN is the auth boundary
- Multi-user support via URL prefix `/u/{user_id}/` routed by `UserRoutingMiddleware` to per-user SQLite databases
- Whoop auth via Cognito (stored in `WhoopToken` table)
- Claude auth via CLI OAuth session on host machine

**Date Handling:**
- All dates as ISO strings (`YYYY-MM-DD`) in Eastern timezone
- `today_eastern()` in `server/config.py` is the canonical date source
- Frontend mirrors with `todayEastern()` using `toLocaleDateString('en-CA', { timeZone: 'America/New_York' })`

**Background Tasks:**
- Whoop biometric sync triggered lazily on first chat of the day (`_maybe_trigger_whoop_sync`)
- Uses `loop.create_task()` for fire-and-forget background work
- systemd timers handle scheduled jobs (morning briefing, whoop sync every 4 hours)

---

*Architecture analysis: 2026-03-23*
