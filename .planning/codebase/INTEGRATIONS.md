# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

### Claude AI (Primary Integration)

**Architecture Decision: CLI subprocess, NOT SDK**

The codebase uses `claude --print` as a subprocess rather than the `anthropic` Python SDK for all AI inference. The `anthropic>=0.40` pip dependency in `pyproject.toml` is vestigial and unused in the main chat flow.

**Why CLI over SDK:**
- Claude Code CLI handles OAuth authentication automatically (no API key management)
- Inherits the user's Claude Code session/subscription
- No need to provision or pay for a separate Anthropic API key
- Trade-off: each request spawns a full OS process (~100-300MB RAM per invocation)

**Binary Location:**
- Resolved at import time: `shutil.which("claude") or "/home/deck/.local/bin/claude"` in `server/services/claude_service.py` line 10
- Current version: 2.1.81, symlinked from `/home/deck/.local/share/claude/versions/2.1.81`

**Subprocess Lifecycle:**

```python
# server/services/claude_service.py, _call_claude() at line 396
proc = await asyncio.create_subprocess_exec(
    CLAUDE_BIN, "--print",
    "--model", MODEL,
    "--append-system-prompt", system_prompt,
    "-p", message,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
```

**Lifecycle details:**
1. **Spawn:** `asyncio.create_subprocess_exec()` forks a new process for every request
2. **Communication:** Pipes stdout/stderr, waits for full completion (no streaming)
3. **Timeout:** 120 seconds hard limit via `asyncio.wait_for()`
4. **Cleanup on timeout:** `proc.kill()` then `await proc.wait()` ensures zombie cleanup
5. **Error handling:** Non-zero exit raises `RuntimeError`, caught by `ClaudeService.chat()`
6. **Output parsing:** `_extract_json()` strips code fences and extracts JSON from raw text

**Concurrency Model:**
- No process pooling or reuse. Each request spawns a fresh `claude` process.
- No concurrency limiter (semaphore/lock). Multiple simultaneous chat requests each spawn their own subprocess.
- The tool-use loop (`_call_claude_with_tools()` at line 423) can spawn up to `MAX_TOOL_ITERATIONS = 3` sequential subprocesses per single user request.
- With Whoop tools connected, a single chat request may invoke 1-3 Claude CLI processes sequentially.

**RAM Implications:**
- Each `claude --print` process loads the full Claude Code runtime (Node.js + dependencies)
- Estimated ~100-300MB RSS per process during execution
- On a Steam Deck (16GB RAM), 2-3 concurrent chat requests could consume 300-900MB
- No process caching or warm-starting between requests
- Processes are short-lived (typical response in 5-30s) and fully cleaned up after

**Model:**
- `claude-sonnet-4-20250514` defined as `MODEL` constant at `server/services/claude_service.py` line 11
- Change in one place only

**Auth/OAuth:**
- Claude CLI uses its own OAuth session stored in `~/.claude/`
- No API key needed or used for the main chat flow
- Docker mounts `~/.claude:/root/.claude:ro` to share host credentials
- `anthropic_api_key` in `server/config.py` exists but is only referenced by legacy routes (`server/routes/layout.py` line 17, `server/routes/video.py` line 20) that pass it to `ClaudeService(api_key=...)` -- these routes appear to be older code paths

**Invocation Points (all in `server/services/claude_service.py`):**
- `ClaudeService.chat()` at line 298 - Main chat endpoint, calls `_call_claude()` or `_call_claude_with_tools()`
- `ClaudeService.generate_interview_questions()` at line 337 - Onboarding interview
- `ClaudeService.analyze_form()` at line 372 - Video form analysis
- `_call_claude_with_tools()` at line 423 - Tool-use loop for Whoop integration (up to 3 iterations)

**Tool-Use Implementation:**
- NOT using Claude's native tool_use API. Tools are described in the system prompt as text.
- Claude returns `tool_calls` as a JSON array in its response body.
- Tool execution happens server-side via `execute_whoop_tool()` in `server/services/whoop_tools.py`.
- Results are fed back as a follow-up message in the next iteration.
- Maximum 3 tool iterations per request (`MAX_TOOL_ITERATIONS` at line 420).

**Context Assembly:**
- `assemble_context()` at line 187 builds a text string from: profile, training memory, training log, active workout, Whoop biometrics, HRV trends, set history, meal totals, conversation history
- System prompt is ~120 lines of coaching rules + context
- Last 10 messages of history included (line 290)
- Target: keep context under ~4000 tokens per request

### Whoop API (Biometrics & Activity Tracking)

**SDK/Client:** `whoop-write-api` (reverse-engineered, installed from git)
- Repository: `https://github.com/jd1207/whoop-write-api`
- Optional dependency group: `pip install -e ".[whoop]"`
- Version: v0.4 with Cognito auth (not OAuth)

**Auth:**
- Cognito login via `CognitoAuth().login(email, password)` in `server/routes/whoop.py` line 39
- Tokens stored in `WhoopToken` table (access_token, refresh_token, expires_at)
- `get_whoop_client(db)` in `server/services/whoop_service.py` line 18 creates a client with auto-refresh callback
- Token refresh persisted to DB via `persist_refreshed_tokens` callback
- Consecutive auth failures tracked in `SystemMemory` key `whoop_status` (`server/cli.py` line 47)

**Integration Pattern (CRITICAL):**
```python
# correct: lazy import inside function, wrapped in try/except
async def some_function(db):
    try:
        from whoop import WhoopClient
        client = get_whoop_client(db)
        # ... do work
    except (ImportError, Exception) as e:
        return {"error": str(e)}

# WRONG: never import at module top level
from whoop import WhoopClient  # breaks if lib not installed
```

**Concurrency:**
- `_sync_lock = asyncio.Lock()` in `server/services/whoop_service.py` line 15 prevents concurrent biometric syncs
- Staleness threshold: 2 hours (`STALENESS_THRESHOLD = 7200`) -- skips sync if data is fresh
- Background sync triggered lazily from chat route via `_maybe_trigger_whoop_sync()` at `server/routes/chat.py` line 22

**Data Flows:**

1. **Biometric Sync (read):**
   - Trigger: systemd timer every 4h, or lazily from chat route
   - `sync_whoop_biometrics()` at `server/services/whoop_service.py` line 46
   - Fetches: recovery, sleep, strain (cycles)
   - Backfills from last synced date
   - Stores in `WhoopData` table

2. **Workout Push (write):**
   - Trigger: workout completion at `server/routes/workout.py` line 152
   - `push_workout_to_whoop()` at `server/services/whoop_service.py` line 127
   - Sends: `DetailedExercise` with `ExerciseSet` data
   - On failure: queued to `WhoopSyncQueue` for retry (max 3 retries)

3. **Journal Sync (write):**
   - Trigger: meal logged with `journal_signals` at `server/routes/chat.py` line 265
   - `sync_journal_to_whoop()` at `server/services/whoop_service.py` line 289
   - Sends: caffeine count, alcohol flag, late meal flag, protein

4. **Tool Execution (read/write):**
   - Trigger: Claude includes `tool_calls` in response during chat
   - `execute_whoop_tool()` at `server/services/whoop_tools.py` line 82
   - Handlers: create_activity, update_weight, set_alarm, delete_activity, list_activities, search_catalog
   - Each handler lazy-imports whoop client

**Graceful Degradation:**
- App must work 100% without Whoop installed or connected
- Whoop availability determined by presence of `WhoopToken` row, NOT env vars
- All Whoop calls wrapped in try/except
- Failed syncs queued to `WhoopSyncQueue` with error details
- `process_whoop_queue()` retries pending items (max 3 attempts)
- Exercise catalog populated on first login, best-effort

### ntfy.sh (Push Notifications)

- Service: ntfy.sh (self-hosted or public)
- Used for: Morning briefing push notifications
- Client: `httpx.AsyncClient` in `server/services/notification_service.py`
- Auth: Topic name stored in `ntfy_topic` setting (env var)
- Triggered by: systemd timer at 07:00 via `server/scripts/morning_briefing.py`

## Data Storage

**Databases:**
- SQLite with WAL mode
  - Main DB: `sqlite:///./spotme.db` (configurable via `DATABASE_URL` env var)
  - Per-user DBs: `sqlite:///./spotme_{user_id}.db` (multi-user support)
  - Connection: `server/config.py` Settings class, `server/database.py`
  - ORM: SQLAlchemy 2.x with sync `Session` (NOT async engine)
  - WAL pragma + busy_timeout=5000ms set on every connection via event listener
  - `check_same_thread=False` for FastAPI async compatibility
  - Per-user engine cache: `_user_engines` dict in `server/database.py` line 27

**SQLite Connection Patterns:**
```python
# server/database.py
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine)

# dependency injection pattern used everywhere:
def get_db():
    user_id = _current_user.get()  # contextvars for multi-user
    if user_id:
        eng = _get_user_engine(user_id)
        db = sessionmaker(bind=eng)()
    else:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Multi-User Routing:**
- `UserRoutingMiddleware` in `server/main.py` line 15 strips `/u/{user_id}/` prefix
- Sets `_current_user` contextvar so `get_db()` returns the correct user's database
- User ID validated: `^[a-zA-Z0-9_-]{1,32}$`
- Engine cache: engines created per-user and cached in `_user_engines` dict (never evicted)

**Schema Migrations:**
- Alembic configured (`alembic.ini`, `alembic/` directory)
- ALSO: inline `ALTER TABLE` migrations in `server/main.py` `create_app()` (lines 43-93) for columns added after initial schema
- Tables auto-created via `Base.metadata.create_all()` for new user databases

**Tables (16 total, defined in `server/models.py`):**
- `programs` - Training program metadata
- `workouts` - Workout sessions with date, type, status
- `exercises` - Exercises within workouts
- `sets` - Individual sets with targets and actuals
- `whoop_data` - Cached biometric data per date
- `form_checks` - Video analysis results
- `conversations` - Chat history with date scoping
- `user_profiles` - Athlete profile and nutrition targets
- `system_memory` - Key-value store (training plan, onboarding flags, whoop status)
- `whoop_tokens` - Cognito auth tokens
- `whoop_sync_queue` - Failed sync retry queue
- `meals` - Meal logs with macros and journal signals
- `exercise_catalog` - Cached Whoop exercise catalog
- `training_log` - Append-only training log entries (completions, notes, adjustments)

**File Storage:**
- Videos saved to `VIDEO_DIR` (default `./videos`)
- ffmpeg extracts frames to temp directory, returned as base64

**Caching:**
- No Redis/Memcached
- Whoop biometric data cached in SQLite with staleness check (2h threshold)
- Exercise catalog cached in `exercise_catalog` table
- Frontend: IndexedDB for offline sets, cached layouts, cached workouts (`frontend/src/db.ts`)
- Frontend: Workbox service worker caches API responses (NetworkFirst, 1h TTL, 50 entries)

## Authentication & Identity

**Auth Provider:** None (Tailscale network boundary)
- No app-level auth -- Tailscale VPN is the auth boundary
- Multi-user support via URL prefix `/u/{user_id}/` but no password/token auth
- Each user gets their own SQLite database file

**Claude Auth:** OAuth via Claude Code CLI
- CLI manages its own OAuth session in `~/.claude/`
- No API key needed for main chat flow
- Docker: mount `~/.claude:/root/.claude:ro`

**Whoop Auth:** AWS Cognito
- Email/password login via `CognitoAuth().login()`
- Tokens stored in `WhoopToken` table per user database
- Auto-refresh via callback in `get_whoop_client()`

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)
- Errors logged to stdout via Python `logging` module

**Logs:**
- Python `logging` with `logger = logging.getLogger(__name__)` pattern
- systemd journal: `journalctl --user -u spotme -f`
- CLI jobs: `logging.basicConfig(level=logging.INFO)` in `server/cli.py`

## CI/CD & Deployment

**Hosting:**
- Steam Deck (primary): systemd user service, Tailscale for remote access
- Docker (alternative): `Dockerfile` and `docker-compose.yml` available

**CI Pipeline:**
- None detected (no GitHub Actions, no CI config files)

**Deploy Process (Steam Deck):**
```bash
systemctl --user restart spotme      # restart server
journalctl --user -u spotme -f       # tail logs
```

**systemd Services (`deploy/`):**
- `spotme.service` - Main uvicorn server on `127.0.0.1:8000`
- `spotme-whoop-sync.service` + `.timer` - Whoop sync every 4 hours
- `spotme-morning.service` + `.timer` - Morning briefing at 07:00

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - SQLite connection string (default: `sqlite:///./spotme.db`)

**Optional env vars:**
- `ANTHROPIC_API_KEY` - Only used by legacy layout/video routes, NOT by main chat
- `VIDEO_DIR` - Video upload directory (default: `./videos`)
- `NTFY_TOPIC` - ntfy.sh push notification topic

**Secrets location:**
- `.env` file at project root (loaded by pydantic-settings)
- Whoop tokens stored in database (WhoopToken table)
- Claude OAuth credentials in `~/.claude/` (managed by CLI)

## Webhooks & Callbacks

**Incoming:**
- None (no webhook endpoints)

**Outgoing:**
- ntfy.sh POST for morning notifications (`server/services/notification_service.py`)
- Morning briefing script calls own API via loopback (`server/scripts/morning_briefing.py` hits `http://127.0.0.1:8000/api/`)

## Process & Resource Summary

**Per chat request resource usage:**
- 1 Claude CLI subprocess (no tools) or 1-3 sequential subprocesses (with tools)
- Each subprocess: ~100-300MB RAM, 5-30s typical duration, 120s hard timeout
- No process pooling, no warm cache, no connection reuse
- SQLite session opened/closed per request via `get_db()` dependency

**Scaling considerations:**
- Single-user design (one person at the gym)
- Multi-user support exists but no concurrency limiting on Claude subprocess spawning
- SQLite WAL mode allows concurrent reads but serializes writes
- No rate limiting on API endpoints
- Steam Deck has 16GB RAM -- practical limit of ~3-5 concurrent Claude processes

---

*Integration audit: 2026-03-23*
