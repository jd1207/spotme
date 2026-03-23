# Codebase Concerns

**Analysis Date:** 2026-03-23

## Tech Debt

### Claude CLI Subprocess Architecture (Critical)

- Issue: Every chat request spawns a fresh `claude --print` subprocess (a 227MB ELF binary at `/home/deck/.local/share/claude/versions/2.1.81`). There is no connection pooling, no session reuse, and no persistent process. Each invocation loads the entire Claude Code runtime, authenticates via stored OAuth credentials in `~/.claude/.credentials.json`, makes an HTTPS request to the Anthropic API, then exits.
- Files: `server/services/claude_service.py` lines 396-417 (`_call_claude`), lines 423-468 (`_call_claude_with_tools`)
- Impact:
  - **RAM**: Each subprocess consumes ~100-200MB RSS. On a Steam Deck with 14GB RAM (10GB in use, 7.7GB swap consumed), even 2-3 concurrent requests could push the system into heavy swapping.
  - **Latency**: Process startup overhead (loading a 227MB binary, initializing Node.js runtime, reading OAuth tokens, establishing TLS connection) adds 2-5 seconds per call before any API work begins.
  - **Tool-use loop**: `_call_claude_with_tools` (line 445) spawns up to 3 **sequential** subprocess invocations per single user request — each with full startup cost. A tool-use chat request can take 30-90 seconds.
  - **No streaming**: The `--print` flag requires the full response to complete before returning. With a 120-second timeout (line 407), the user sees nothing until the entire response is ready.
- Fix approach: Replace `claude --print` subprocess calls with direct use of the `anthropic` Python SDK (already listed as a dependency in `pyproject.toml`: `"anthropic>=0.40"`). This eliminates process spawning entirely:
  ```python
  # current: subprocess per call
  proc = await asyncio.create_subprocess_exec(CLAUDE_BIN, "--print", ...)

  # target: single async client, persistent connection
  client = anthropic.AsyncAnthropic()  # uses ANTHROPIC_API_KEY env var
  response = await client.messages.create(model=MODEL, system=system, messages=[...])
  ```
  The SDK supports streaming (`client.messages.stream()`), connection reuse via httpx connection pooling, and native tool-use without the text-based workaround. The `ANTHROPIC_API_KEY` is already configured in `server/config.py` line 4 as `anthropic_api_key`.

### Text-Based Tool-Use Workaround

- Issue: Instead of using the Anthropic API's native tool-use protocol (`tools` parameter in messages API), the code embeds tool descriptions as text in the system prompt (lines 432-441) and asks Claude to return `tool_calls` as a JSON array in its text response. This is fragile — tool calls depend on Claude correctly formatting JSON within its response text, and the server must parse them from the response.
- Files: `server/services/claude_service.py` lines 432-468
- Impact: Tool calls can fail silently if Claude doesn't format the JSON correctly. The follow-up message (line 450) loses conversation context — each tool iteration is a fresh stateless call with only the tool results, not the original user message or conversation history. Native tool-use maintains conversation state across tool calls.
- Fix approach: Use `anthropic.AsyncAnthropic` with the `tools` parameter. The SDK handles tool-use turns natively with proper `tool_use` and `tool_result` content blocks:
  ```python
  response = await client.messages.create(
      model=MODEL, system=system, messages=messages,
      tools=[{"name": "...", "description": "...", "input_schema": {...}}],
  )
  # SDK returns tool_use blocks directly, no JSON parsing needed
  ```

### Stale `ClaudeService` Constructor Signatures

- Issue: `ClaudeService` has no `__init__` method and does not accept any parameters, but two call sites pass `api_key=settings.anthropic_api_key` as a keyword argument.
- Files:
  - `server/routes/video.py` line 20: `ClaudeService(api_key=settings.anthropic_api_key)`
  - `server/routes/layout.py` line 19: `ClaudeService(api_key=settings.anthropic_api_key)`
- Impact: These `api_key` arguments are silently ignored. The class works only because it delegates to `_call_claude()` which uses the CLI binary (inheriting OAuth from the filesystem). The `api_key` parameter is a vestige from when the service used the Anthropic SDK directly.
- Fix approach: Either add `__init__(self, api_key=None)` to `ClaudeService` or remove the `api_key=` arguments from call sites. When migrating to the SDK, the `api_key` parameter becomes meaningful again.

### Inline Schema Migrations in `main.py`

- Issue: `server/main.py` lines 43-100 contain 15+ `ALTER TABLE` statements wrapped in column-existence checks, executed on every app startup. This is a manual migration system running alongside (and duplicating) the Alembic migration framework already configured in `alembic/`.
- Files: `server/main.py` lines 43-100
- Impact: These migrations run on every cold start, adding ~100ms of startup latency. More critically, they can conflict with Alembic migrations — if Alembic adds a column that also exists in the startup code, one or the other will error or silently no-op. The pattern also doesn't support rollbacks.
- Fix approach: Convert all inline `ALTER TABLE` statements to proper Alembic migrations. Remove the startup migration code from `create_app()`. Run `alembic upgrade head` as a deployment step.

### `UserRoutingMiddleware` Per-User Database Without Migrations

- Issue: `server/database.py` lines 32-51 create per-user SQLite databases (`spotme_{user_id}.db`) on first access via `_get_user_engine()`. These databases get `Base.metadata.create_all()` but skip all the inline migrations in `main.py` (calorie_target, protein_target, conversation date, set columns, meal columns, whoop columns).
- Files: `server/database.py` lines 32-51, `server/main.py` lines 43-100
- Impact: Per-user databases lack columns that the main database has. Any query touching those columns will crash with `OperationalError: no such column`. The feature appears partially implemented — the middleware exists but the migration gap makes it broken for real use.
- Fix approach: Either remove the per-user database feature if unused, or ensure migrations run against all user databases (another argument for consolidating into Alembic).

## Security Considerations

### SQL Injection via `ilike` in Exercise Catalog Search

- Risk: `server/services/whoop_tools.py` line 63-64 passes user-controlled `query` directly into an `ilike` pattern without escaping SQL wildcards:
  ```python
  query = params["query"].lower()
  results = db.query(ExerciseCatalog).filter(
      ExerciseCatalog.name.ilike(f"%{query}%")
  )
  ```
  The `query` string originates from Claude's tool-call arguments, which are AI-generated text based on user input. While SQLAlchemy parameterizes the value (preventing SQL injection), the `%` and `_` wildcards within the LIKE pattern are not escaped — a query containing `%` will match everything.
- Files: `server/services/whoop_tools.py` lines 63-64
- Current mitigation: SQLAlchemy parameterization prevents actual SQL injection. The risk is limited to unexpected wildcard matching.
- Recommendations: Escape `%` and `_` in the query string before building the LIKE pattern.

### Silent Exception Swallowing

- Risk: Multiple `except Exception: pass` blocks silently discard errors with no logging, making failures invisible.
- Files:
  - `server/routes/chat.py` lines 40-41: Whoop sync failure silently ignored
  - `server/routes/chat.py` lines 271-272: Journal sync failure silently ignored
  - `server/routes/layout.py` lines 23-24: Claude layout generation failure silently ignored
- Current mitigation: The app continues functioning (graceful degradation for Whoop).
- Recommendations: Add `logger.debug()` or `logger.warning()` to every bare `except` block. Silent failures make debugging production issues nearly impossible.

### CORS Wildcard

- Risk: `server/main.py` line 38 sets `allow_origins=["*"]` which permits any origin to make authenticated requests.
- Files: `server/main.py` line 38
- Current mitigation: The app has no authentication — Tailscale is the auth boundary. This is acceptable for the current single-user deployment but would be a critical issue if the app were exposed publicly.
- Recommendations: Restrict CORS to the Tailscale IP range or the known frontend origin when moving beyond single-user.

## Performance Bottlenecks

### Chat Endpoint Response Time

- Problem: A single `/api/chat` request with Whoop connected triggers: 6 DB queries for context assembly, 1-3 Claude CLI subprocess spawns (each 5-30 seconds), plus DB writes for conversation, profile, meal, training log, and onboarding flags. Total wall time is 10-60 seconds.
- Files: `server/routes/chat.py` lines 82-280, `server/services/claude_service.py` lines 298-335
- Cause: Sequential subprocess calls with full startup overhead per call. The chat endpoint also does synchronous DB queries within an async handler.
- Improvement path:
  1. Migrate to Anthropic SDK (eliminates process startup, enables streaming)
  2. Use streaming responses (`text/event-stream`) so the user sees tokens as they arrive
  3. Move post-response side effects (Whoop sync, onboarding flags) to background tasks

### Context Assembly Does N+1 Queries

- Problem: `assemble_context()` in `server/services/claude_service.py` lines 187-293 accepts a `db` parameter and performs additional queries inline (HRV average at line 239, stale data check at line 248, WhoopToken check at line 257, ExerciseCatalog check at line 259, SystemMemory checks at lines 265-277). The caller in `server/routes/chat.py` has already queried most of this data.
- Files: `server/services/claude_service.py` lines 236-277, `server/routes/chat.py` lines 82-170
- Cause: Context assembly grew organically — new features added new queries inside the function rather than passing data in from the route.
- Improvement path: Have the route handler fetch all needed data upfront and pass it to `assemble_context()` as parameters. Remove `db` parameter from `assemble_context()` entirely — a pure function that takes data and returns a string.

### `_maybe_trigger_whoop_sync` Creates Uncollected Background Tasks

- Problem: `server/routes/chat.py` lines 22-47 creates a fire-and-forget async task via `loop.create_task(_do_sync())`. The task creates its own `SessionLocal()` database session. If the task fails, the exception is silently swallowed. If the task takes long, there is no tracking or timeout.
- Files: `server/routes/chat.py` lines 22-47
- Cause: Background Whoop sync was added as a quick fix to avoid blocking the chat response.
- Improvement path: Use FastAPI's `BackgroundTasks` dependency instead of raw `loop.create_task()`. This integrates with the framework's lifecycle and error handling.

## Fragile Areas

### JSON Parsing from Claude CLI Output

- Files: `server/services/claude_service.py` lines 379-393 (`_extract_json`), lines 318-321 (fallback on parse failure)
- Why fragile: The `_extract_json` function uses regex to find JSON in Claude's text output, handling code fences (`\`\`\`json ... \`\`\``), raw JSON, and embedded JSON. This is necessary because `claude --print` returns raw text that may include markdown formatting. Any change to Claude CLI's output format (adding prefixes, changing fence format) breaks parsing.
- Safe modification: When migrating to the SDK, `_extract_json` becomes unnecessary — the SDK returns structured `Message` objects with typed content blocks.
- Test coverage: `tests/test_claude_sdk.py` covers basic JSON and fenced JSON extraction. No test for malformed JSON within otherwise valid output.

### Tool-Use Context Loss Between Iterations

- Files: `server/services/claude_service.py` lines 445-468
- Why fragile: Each tool-use iteration calls `_call_claude()` with a fresh system prompt + message. The follow-up (line 450) sends only tool results — it does not include the original user message, prior Claude response, or any conversation state. Claude must reconstruct intent from tool results alone. This frequently causes responses that lose the original question's context.
- Safe modification: Accumulate messages across iterations. When migrating to SDK, use the native multi-turn conversation format where each tool-use/tool-result pair is a message in the conversation.
- Test coverage: `tests/test_claude_sdk.py` has one tool-use test but does not test context preservation across iterations.

### `ensure_future` for Journal Sync

- Files: `server/routes/chat.py` line 270
- Why fragile: `asyncio.ensure_future(sync_journal_to_whoop(db, request_date))` passes the **same** `db` session to a background coroutine. The session was yielded by `get_db()` and will be closed when the request handler returns (via the `finally: db.close()` in `server/database.py` line 63). The background task may try to use a closed session, causing `StatementError` or `ObjectDeletedError`.
- Safe modification: Create a new `SessionLocal()` for background tasks (like `_maybe_trigger_whoop_sync` does on line 36). Better yet, use FastAPI `BackgroundTasks`.
- Test coverage: No test covers this race condition.

## Scaling Limits

### SQLite Concurrent Write Locking

- Current capacity: Single-user app with sequential requests. WAL mode enabled (`server/database.py` line 19) with 5-second busy timeout (line 20).
- Limit: SQLite allows only one writer at a time. With WAL mode, readers don't block writers, but concurrent writes queue behind the 5-second timeout. If a long Claude response (up to 120 seconds) holds a transaction, other writes will timeout with `OperationalError: database is locked`.
- Scaling path: The current single-user, single-device use case is fine. If adding multi-user support, switch to PostgreSQL or add explicit write serialization. The per-user database approach in `server/database.py` partially addresses this by isolating user data.

### Claude CLI Process Concurrency

- Current capacity: The Steam Deck has 14GB RAM total, ~4.4GB available. Each `claude --print` subprocess uses ~100-200MB.
- Limit: More than ~10 concurrent chat requests would consume available memory. With the tool-use loop potentially spawning 3 processes per request, 3-4 concurrent users could exhaust memory.
- Scaling path: Migrate to the Anthropic SDK — a single persistent `httpx.AsyncClient` handles unlimited concurrent requests with ~0 additional memory per request.

### Context Size Growth

- Current capacity: Estimated ~4,200 tokens per request (system prompt: ~1,900 tokens, context assembly: ~2,100 tokens, tool descriptions: ~225 tokens). Well within the ~4,000-token target mentioned in `CLAUDE.md`.
- Limit: The training plan (`system_memory.content`) is currently 2,649 chars (~660 tokens). If a user stores a detailed multi-month program, this could grow to 10,000+ chars. The history window is capped at 10 messages (line 291) with 200-char truncation per message (line 291), limiting that axis. Training log shows last 15 entries (line 216). These caps are reasonable.
- Scaling path: Add explicit token counting before sending to Claude. Truncate or summarize the training plan if it exceeds a threshold. Consider a sliding window for training log entries based on recency and relevance.

## Dependencies at Risk

### Claude Code CLI as API Gateway

- Risk: The entire AI integration depends on `claude --print`, a CLI tool designed for interactive developer use, not as a programmatic API gateway. CLI output format, authentication flow, and command-line flags can change between versions without notice. The current version is 2.1.81.
- Impact: Any Claude Code update could break the app's core functionality. There is no version pinning — the binary at `/home/deck/.local/bin/claude` is a symlink to the latest installed version.
- Migration plan: Replace with `anthropic` Python SDK (`anthropic>=0.40`, already in dependencies). The SDK has a stable, versioned API with semantic versioning guarantees. This is the single highest-priority migration.

### `whoop-write-api` (Reverse-Engineered)

- Risk: Installed from git (`git+https://github.com/jd1207/whoop-write-api.git`). Uses Cognito auth against Whoop's undocumented internal API. Can break when Whoop updates their API or auth flow.
- Impact: Whoop integration stops working. The app is designed to degrade gracefully (lazy imports, try/except everywhere), so core functionality continues.
- Migration plan: Already well-mitigated by the graceful degradation pattern. Monitor for breakage. No official Whoop write API exists.

## Missing Critical Features

### No Request Rate Limiting

- Problem: No rate limiting on any endpoint. A misbehaving client (or accidental rapid taps in the PWA) could spawn dozens of concurrent Claude subprocesses.
- Blocks: Safe deployment to multiple users. A single user accidentally double-tapping the send button spawns two expensive Claude calls.
- Fix: Add a semaphore or rate limiter. Simplest approach: `asyncio.Semaphore(2)` around Claude calls to limit concurrent subprocesses.

### No Response Streaming

- Problem: The `claude --print` flag requires the full response before returning. Users wait 10-60 seconds with no feedback.
- Blocks: Good UX during workout sessions where the user is between sets and needs quick responses.
- Fix: The Anthropic SDK supports streaming via `client.messages.stream()`. Return a `StreamingResponse` from FastAPI. The frontend already handles text display incrementally.

### No Health Check or Process Monitoring

- Problem: No `/health` endpoint. No monitoring of running Claude subprocesses. No alerting when the system is under memory pressure.
- Blocks: Reliable operation as a systemd service. If the service OOMs, systemd restarts it but there is no early warning.
- Fix: Add a `/health` endpoint that reports memory usage, active subprocess count, and database connectivity. Configure systemd `MemoryMax=` to prevent OOM kills.

## Test Coverage Gaps

### No Integration Test for Full Chat Flow

- What's not tested: The `/api/chat` endpoint's full flow (context assembly, Claude call, profile save, meal save, training log save, Whoop sync) is not tested end-to-end. Individual pieces are tested in isolation.
- Files: `tests/test_chat.py` tests `assemble_context` and helper functions. `tests/test_claude_sdk.py` tests `_call_claude` and `_call_claude_with_tools` with mocked subprocesses. No test creates a `ChatRequest`, POSTs to `/api/chat`, and verifies all side effects.
- Risk: Regressions in the interaction between context assembly, Claude response parsing, and database writes go undetected.
- Priority: High

### No Test for Concurrent Request Handling

- What's not tested: Behavior when multiple chat requests arrive simultaneously — subprocess resource exhaustion, SQLite locking, session sharing between background tasks.
- Files: No file covers this.
- Risk: The app could OOM or deadlock under concurrent load with no test to catch it.
- Priority: Medium (single-user app, but double-tap is a real scenario)

### No Test for Background Task Session Safety

- What's not tested: The `ensure_future(sync_journal_to_whoop(db, ...))` pattern in `server/routes/chat.py` line 270 shares a database session with a background task that outlives the request.
- Files: `tests/test_chat.py` does not test background task execution.
- Risk: `StatementError` or `ObjectDeletedError` in production when the background task uses the closed session.
- Priority: High

### No Test for Claude CLI Timeout/Kill

- What's not tested: The timeout path in `_call_claude` (lines 408-411) kills the process and raises `RuntimeError`. No test verifies that the process is actually cleaned up and that the error propagates correctly through `ClaudeService.chat()` to the route handler's catch-all.
- Files: `tests/test_claude_sdk.py` tests CLI error (non-zero exit) but not the timeout path.
- Risk: Orphaned claude processes accumulating if `proc.kill()` doesn't fully terminate the process tree.
- Priority: Medium

---

*Concerns audit: 2026-03-23*
