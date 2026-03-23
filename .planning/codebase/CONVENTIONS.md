# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Files:**
- snake_case for all Python files: `claude_service.py`, `workout_sequencer.py`, `program_parser.py`
- Test files mirror source with `test_` prefix: `test_chat.py`, `test_claude_sdk.py`, `test_whoop.py`
- Routes named for the resource: `server/routes/chat.py`, `server/routes/workout.py`
- Services named for the integration: `server/services/claude_service.py`, `server/services/whoop_service.py`

**Functions:**
- snake_case everywhere: `assemble_context()`, `get_next_set()`, `push_workout_to_whoop()`
- Private helpers prefixed with `_`: `_call_claude()`, `_extract_json()`, `_get_today_whoop()`, `_find_plan()`
- Route handler names match the HTTP path: `chat()` for `/chat`, `morning_briefing()` for `/morning`
- Async for all route handlers and Claude/Whoop calls. Sync for pure DB operations.

**Variables:**
- snake_case: `recovery_score`, `workout_plan`, `meal_totals`
- Constants are UPPER_SNAKE_CASE: `SYSTEM_PROMPT`, `CLAUDE_BIN`, `MODEL`, `MAX_TOOL_ITERATIONS`, `VALID_COMPONENT_TYPES`
- Abbreviations kept lowercase: `db`, `hrv`, `rpe`, `e1rm`

**Types/Classes:**
- PascalCase: `ClaudeService`, `ChatRequest`, `ChatResponse`, `WhoopData`
- SQLAlchemy models are singular nouns: `Program`, `Workout`, `Exercise`, `Set`, `Meal`
- Pydantic schemas use Request/Response suffix: `ChatRequest`, `WorkoutCompleteResponse`

## Code Style

**Formatting:**
- ruff listed in dev dependencies (`pyproject.toml`) but no `[tool.ruff]` config section defined
- No `.prettierrc`, `.editorconfig`, or formatting config files detected
- Implicit 4-space indentation (Python standard)
- No enforced line length -- some lines exceed 120 chars

**Linting:**
- ruff available but no explicit rule config
- No pre-commit hooks or CI pipeline configured

## Import Organization

**Order (observed pattern):**
1. Standard library: `import asyncio`, `import json`, `import logging`, `import re`
2. Third-party: `from fastapi import APIRouter`, `from sqlalchemy.orm import Session`
3. Internal: `from server.database import get_db`, `from server.models import Workout`

**Lazy imports for unstable dependencies:**
```python
# whoop is ALWAYS lazy-imported inside functions
async def sync_whoop(db):
    try:
        from whoop import WhoopClient
        # ... use client
    except (ImportError, Exception):
        return {"error": str(e)}
```
This pattern is mandatory for the `whoop` package. See `server/services/whoop_tools.py` and `server/services/whoop_service.py`.

**Path Aliases:**
- None. All imports use full paths from `server.*` root.

## Claude Integration Pattern

**Subprocess-based, not SDK:**
Claude is invoked via CLI subprocess (`claude --print`), NOT the Anthropic Python SDK. This is because SpotMe uses Claude Code's OAuth session rather than an API key.

```python
# server/services/claude_service.py, lines 396-417
CLAUDE_BIN = shutil.which("claude") or "/home/deck/.local/bin/claude"

async def _call_claude(system_prompt: str, message: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--model", MODEL,
        "--append-system-prompt", system_prompt,
        "-p", message,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    # ...
    raw = stdout.decode().strip()
    return _extract_json(raw)
```

**Response schema (Claude JSON contract):**
```json
{
  "response": "coaching text (required)",
  "layout": null,
  "set_suggestion": null,
  "profile": null,
  "memory_update": null,
  "training_log_entry": null,
  "meal": null,
  "workout_plan": null,
  "journal_signals": null
}
```
All fields except `response` are optional. `ClaudeService.chat()` in `server/services/claude_service.py` (lines 318-335) extracts each field with `.get()` and returns a normalized dict.

**JSON extraction from CLI output:**
`_extract_json()` in `server/services/claude_service.py` (lines 379-393) strips markdown fences and extracts JSON from mixed text. Handles:
- Raw JSON starting with `{`
- Code-fenced JSON: `` ```json {...} ``` ``
- JSON embedded in prose text

**Error handling cascade:**
1. Subprocess failure (non-zero exit) -> `RuntimeError`
2. Timeout (120s) -> process killed, `RuntimeError`
3. `ClaudeService.chat()` catches all exceptions -> returns fallback dict with error message
4. JSON parse failure -> returns raw text as `response` with all other fields null

**Tool use (Whoop tools):**
Tool descriptions are embedded in the system prompt text (not native Claude tool_use). Claude returns `tool_calls` array in JSON. Max 3 tool iterations. See `_call_claude_with_tools()` in `server/services/claude_service.py` (lines 423-468).

## Context Assembly

`assemble_context()` in `server/services/claude_service.py` (lines 187-293) builds a text context string. Order:
1. User profile (or "NO USER PROFILE YET" prompt)
2. Training memory (stored program)
3. Training log (last 15 entries)
4. Active workout context
5. Whoop biometrics with recovery zone
6. HRV trend (7-day average comparison)
7. Stale data flag
8. Tool/catalog availability flags
9. Onboarding education messages
10. Recent set history (last 15 completed sets)
11. Today's meal totals
12. Conversation history (last 10 messages)

## Error Handling

**Patterns:**

**Graceful degradation for external services:**
```python
# whoop calls always wrapped in try/except
try:
    result = await push_workout_to_whoop(db, workout.id)
except ImportError:
    whoop_error = "whoop-write-api not installed"
except Exception as e:
    whoop_error = str(e)
```

**Failed syncs queue for retry:**
```python
# server/services/whoop_service.py
def _queue_failed_sync(db, workout_id, date, error, sync_type="workout"):
    db.add(WhoopSyncQueue(
        workout_id=workout_id,
        payload=json.dumps({"date": date}),
        status="pending",
        last_error=str(error),
        sync_type=sync_type,
    ))
```

**Claude fallback response pattern:**
```python
return {
    "response": "Having trouble reaching Claude right now. Try again in a sec.",
    "layout": None, "profile": None, "memory_update": None,
    "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None,
}
```

## Logging

**Framework:** Python `logging` module

**Pattern:**
```python
logger = logging.getLogger(__name__)
# lowercase messages, no periods, format strings with %s
logger.error("claude call failed: %s", e)
logger.warning("whoop tool %s failed: %s", name, e)
logger.info("queued failed whoop sync for workout %s", workout_id)
```

## Comments

**When to Comment:**
- Inline comments are rare and lowercase
- Docstrings used sparingly for non-obvious functions
- Section comments with `# --` separators in test files

**Docstring style:**
```python
async def _call_claude_with_tools(...) -> str:
    """call claude with tool-use via CLI, parsing tool calls from JSON response."""
```

## Function Design

**Size:** Most functions are under 50 lines. `chat()` route handler in `server/routes/chat.py` is the longest at ~200 lines (orchestrates many side effects).

**Parameters:** Use keyword arguments for optional params. DB session always via `Depends(get_db)` in routes.

**Return Values:** Route handlers return dicts or Pydantic models. Service functions return dicts with status fields like `{"synced": True}` or `{"error": "message"}`.

## Module Design

**Exports:** No `__all__` definitions. Imports are explicit.

**Barrel Files:** `server/routes/__init__.py` and `server/services/__init__.py` are empty. Routers are imported individually in `server/main.py`.

## Database Patterns

**Session management:**
- Routes use `db: Session = Depends(get_db)` dependency injection
- In-memory SQLite with `StaticPool` for tests
- `dependency_overrides[get_db]` to inject test sessions

**Mutation pattern:** Direct attribute assignment on ORM objects, then `db.commit()`:
```python
if memory_row:
    memory_row.content = memory_update
else:
    db.add(SystemMemory(key=MEMORY_KEY, content=memory_update))
db.commit()
```

**Date handling:** All dates stored as ISO strings (`YYYY-MM-DD`), converted via `today_eastern()` from `server/config.py`.

## Route Registration

All routers registered in `server/main.py` under `/api` prefix:
```python
app.include_router(chat_router, prefix="/api")
app.include_router(workout_router, prefix="/api")
# ... etc
```

---

*Convention analysis: 2026-03-23*
