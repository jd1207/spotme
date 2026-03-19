# Whoop v0.4 Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate whoop-write-api v0.4 with unified Cognito auth, automatic workout/journal syncing, Claude tool-use for ad-hoc writes, and active biometric coaching.

**Architecture:** Hybrid approach — deterministic auto-sync in the service layer for workouts and journal entries, Claude tool-use for ad-hoc writes (sauna, weight, alarm). Cache-first reads with smart sync triggers. Claude acts as an active coach using Whoop biometrics.

**Tech Stack:** Python/FastAPI, Anthropic SDK (`anthropic.AsyncAnthropic`), whoop-write-api v0.4, SQLAlchemy 2.x (sync), Alembic, React/TypeScript PWA.

**Spec:** `docs/superpowers/specs/2026-03-18-whoop-v04-integration-design.md`

---

## PR Structure

This plan ships as 4 PRs, each independently testable:

| PR | Name | Depends On | Tasks |
|----|------|------------|-------|
| 1 | Anthropic SDK Migration | — | 1-2 |
| 2 | Cognito Auth + Schema | PR 1 | 3-6 |
| 3 | Tool-Use Loop + Auto-Sync + Catalog | PR 2 | 7-13 |
| 4 | Coaching + Journal + Frontend | PR 3 | 14-18 |

---

## File Structure

### New Files
- `alembic/` — Alembic migration infrastructure
- `alembic/env.py` — Migration environment config
- `alembic/versions/001_baseline.py` — Baseline schema snapshot
- `alembic/versions/002_whoop_v04.py` — v0.4 schema additions
- `server/services/whoop_tools.py` — Claude tool handler dispatch
- `tests/test_claude_sdk.py` — SDK migration tests
- `tests/test_whoop_tools.py` — Tool dispatch tests

### Modified Files
- `server/services/claude_service.py` — Replace CLI subprocess with SDK, add tool-use loop
- `server/services/whoop_service.py` — `get_whoop_client()` factory, `whoop_operation()`, smart sync
- `server/routes/whoop.py` — Cognito login, remove OAuth routes
- `server/routes/workout.py` — Auto-sync with DetailedExercise on complete
- `server/routes/chat.py` — Tool-use loop integration, journal signal extraction
- `server/models.py` — New columns and tables per spec
- `server/config.py` — Remove Whoop env vars
- `tests/test_whoop.py` — Update mocks for v0.4
- `frontend/src/api.ts` — Remove OAuth/test-write methods
- `frontend/src/screens/profile.tsx` — Single Cognito login, collapsible stats
- `frontend/src/components/context-banner.tsx` — Stale label, disconnected state

---

## PR 1: Anthropic SDK Migration

### Task 1: Replace `_call_claude()` with Anthropic SDK

**Files:**
- Modify: `server/services/claude_service.py:136-208`
- Create: `tests/test_claude_sdk.py`

The current `_call_claude()` (line 189-208) shells out to the `claude` CLI binary via `asyncio.create_subprocess_exec`. Replace with direct SDK calls. This is a drop-in replacement — same inputs, same outputs, no behavioral changes.

- [ ] **Step 1: Write failing test for SDK-based chat**

```python
# tests/test_claude_sdk.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_call_claude_returns_json_response():
    """_call_claude uses Anthropic SDK and returns parsed JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"response": "test reply", "layout": null}')]
    mock_response.stop_reason = "end_turn"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from server.services.claude_service import _call_claude
        result = await _call_claude("test system prompt", "hello")

        assert '"response"' in result
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == "test system prompt"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_claude_sdk.py::test_call_claude_returns_json_response -v
```

Expected: FAIL (current `_call_claude` uses subprocess, not SDK)

- [ ] **Step 3: Implement SDK-based `_call_claude()`**

Replace `_call_claude()` in `server/services/claude_service.py` (lines 189-208):

```python
import anthropic

MODEL = "claude-sonnet-4-20250514"

async def _call_claude(system_prompt: str, message: str) -> str:
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    )
    raw = response.content[0].text
    return _extract_json(raw.strip())
```

Also update `ClaudeService.__init__()` (line 137-138) to remove the api_key storage since the SDK reads `ANTHROPIC_API_KEY` from env automatically.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_claude_sdk.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/claude_service.py tests/test_claude_sdk.py
git commit -m "refactor: replace claude CLI subprocess with Anthropic SDK"
```

---

### Task 2: Verify existing tests still pass

**Files:**
- No changes — verification only

- [ ] **Step 1: Run full test suite**

```bash
pytest -x --tb=short
```

Expected: All existing tests pass. The mock pattern in existing tests should still work since they mock at the service level, not at `_call_claude` directly.

- [ ] **Step 2: Fix any failures**

If any tests import or mock the old subprocess-based `_call_claude`, update them to mock the SDK call instead:

```python
# old pattern:
with patch("asyncio.create_subprocess_exec"):

# new pattern:
with patch("server.services.claude_service.anthropic") as mock:
    mock.AsyncAnthropic.return_value.messages.create = AsyncMock(return_value=...)
```

- [ ] **Step 3: Commit fixes if any**

```bash
git add -A
git commit -m "test: update mocks for Anthropic SDK migration"
```

---

## PR 2: Cognito Auth + Schema Migration

### Task 3: Initialize Alembic

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/001_baseline.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd /home/deck/spotme
alembic init alembic
```

- [ ] **Step 2: Configure `alembic/env.py`**

Edit `alembic/env.py` to import the SpotMe models and database URL:

```python
from server.models import Base
from server.config import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

- [ ] **Step 3: Configure `alembic.ini`**

Set the SQLAlchemy URL in `alembic.ini`:

```ini
sqlalchemy.url = sqlite:///spotme.db
```

- [ ] **Step 4: Stamp current schema as baseline**

Don't autogenerate against the live DB (it would try to recreate existing tables). Instead, stamp current state:

```bash
alembic stamp head
```

This marks the current DB as up-to-date without running any migrations.

- [ ] **Step 5: Commit**

```bash
git add alembic/ alembic.ini
git commit -m "chore: initialize Alembic for database migrations"
```

---

### Task 4: Add v0.4 schema changes

**Files:**
- Create: `alembic/versions/002_whoop_v04.py`
- Modify: `server/models.py:14-137`

- [ ] **Step 1: Add new columns and table to models.py**

Add to `Exercise` model (after line 32):
```python
whoop_exercise_id = Column(String, nullable=True)
```

Add to `Workout` model (after line 24):
```python
whoop_activity_id = Column(String, nullable=True)
```

Add to `Meal` model (after line 137):
```python
journal_signals = Column(Text, nullable=True)  # JSON: {"caffeine": int, "alcohol": bool}
```

Modify `WhoopSyncQueue` model — make `workout_id` nullable and add `sync_type`:
```python
workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=True)
sync_type = Column(String, default="workout")  # workout, journal, activity
```

Add new `ExerciseCatalog` model:
```python
class ExerciseCatalog(Base):
    __tablename__ = "exercise_catalog"
    id = Column(Integer, primary_key=True)
    whoop_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    equipment = Column(String, nullable=True)
    muscle_group = Column(String, nullable=True)
    cached_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Create Alembic migration**

```bash
alembic revision --autogenerate -m "whoop v0.4 schema additions"
```

Review the generated migration to verify it only adds columns/tables, doesn't drop existing ones.

- [ ] **Step 3: Run migration**

```bash
alembic upgrade head
```

- [ ] **Step 4: Write test verifying new columns exist**

```python
# add to tests/test_whoop.py
def test_v04_schema_columns(db):
    """Verify v0.4 columns exist on models."""
    from server.models import Exercise, Workout, Meal, WhoopSyncQueue, ExerciseCatalog
    # these will fail at import if columns don't exist on the model
    ex = Exercise(name="test", whoop_exercise_id="BENCHPRESS_BARBELL")
    w = Workout(date="2026-03-18", status="active", whoop_activity_id="uuid-123")
    m = Meal(date="2026-03-18", journal_signals='{"caffeine": 1}')
    sq = WhoopSyncQueue(sync_type="journal", status="pending", payload="{}")
    ec = ExerciseCatalog(whoop_id="BENCHPRESS_BARBELL", name="Bench Press")
    db.add_all([ex, w, m, sq, ec])
    db.commit()
    assert ex.whoop_exercise_id == "BENCHPRESS_BARBELL"
    assert w.whoop_activity_id == "uuid-123"
    assert ec.name == "Bench Press"
```

- [ ] **Step 5: Run test**

```bash
pytest tests/test_whoop.py::test_v04_schema_columns -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/models.py alembic/versions/
git commit -m "feat: add v0.4 schema — exercise catalog, whoop_activity_id, journal_signals"
```

---

### Task 5: Implement Cognito auth + client factory

**Files:**
- Modify: `server/services/whoop_service.py:13-25`
- Modify: `server/routes/whoop.py:202-222`
- Modify: `server/config.py:4-10`

- [ ] **Step 1: Write failing test for `get_whoop_client()`**

```python
# add to tests/test_whoop.py
def test_get_whoop_client_from_db_token(db):
    """get_whoop_client loads tokens from WhoopToken table."""
    from datetime import datetime, timedelta
    from server.models import WhoopToken

    db.add(WhoopToken(
        access_token="test-access",
        refresh_token="test-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.commit()

    with patch("whoop.WhoopClient") as MockClient:  # patch at source (lazy import)
        from server.services.whoop_service import get_whoop_client
        client = get_whoop_client(db)
        MockClient.assert_called_once()
        call_kwargs = MockClient.call_args[1]
        assert call_kwargs["token_set"].access_token == "test-access"
        assert call_kwargs["on_token_refresh"] is not None


def test_get_whoop_client_no_token(db):
    """get_whoop_client raises when no token stored."""
    from server.services.whoop_service import get_whoop_client
    with pytest.raises(Exception, match="whoop not connected"):
        get_whoop_client(db)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_whoop.py::test_get_whoop_client_from_db_token -v
pytest tests/test_whoop.py::test_get_whoop_client_no_token -v
```

Expected: FAIL

- [ ] **Step 3: Implement `get_whoop_client()` in whoop_service.py**

Replace `create_whoop_client()` (lines 13-25) with:

```python
from datetime import datetime
from fastapi import HTTPException

def get_whoop_client(db):
    """create a whoop client with auto-refresh from stored tokens."""
    from whoop import WhoopClient, TokenSet

    stored = db.query(WhoopToken).first()
    if not stored:
        raise HTTPException(400, "whoop not connected — login first")

    token_set = TokenSet(
        access_token=stored.access_token,
        refresh_token=stored.refresh_token,
        expires_at=stored.expires_at.timestamp(),
    )

    def persist_refreshed_tokens(new_tokens):
        stored.access_token = new_tokens.access_token
        stored.refresh_token = new_tokens.refresh_token
        stored.expires_at = datetime.fromtimestamp(new_tokens.expires_at)
        db.commit()

    return WhoopClient(
        token_set=token_set,
        on_token_refresh=persist_refreshed_tokens,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_whoop.py::test_get_whoop_client_from_db_token -v
pytest tests/test_whoop.py::test_get_whoop_client_no_token -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for Cognito login route**

```python
# add to tests/test_whoop.py
def test_cognito_login(test_app, db):
    """POST /api/whoop/login authenticates via Cognito and stores tokens."""
    mock_tokens = MagicMock()
    mock_tokens.access_token = "cognito-access"
    mock_tokens.refresh_token = "cognito-refresh"
    mock_tokens.expires_at = 1710000000.0

    with patch("whoop.CognitoAuth") as MockAuth:  # patch at source (lazy import inside route)
        mock_auth = AsyncMock()
        MockAuth.return_value = mock_auth
        mock_auth.login = AsyncMock(return_value=mock_tokens)

        response = test_app.post("/api/whoop/login", json={
            "email": "test@example.com",
            "password": "testpass"
        })

    assert response.status_code == 200
    assert response.json()["connected"] is True

    token = db.query(WhoopToken).first()
    assert token.access_token == "cognito-access"
    assert token.refresh_token == "cognito-refresh"
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_whoop.py::test_cognito_login -v
```

Expected: FAIL (current login route uses WhoopAuth.login_password, not CognitoAuth)

- [ ] **Step 7: Implement Cognito login route**

Replace the login route in `server/routes/whoop.py` (lines 202-222):

```python
@router.post("/whoop/login")
async def whoop_login(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    try:
        from whoop import CognitoAuth, WhoopAuthError
        auth = CognitoAuth()
        tokens = await auth.login(body["email"], body["password"])
    except ImportError:
        raise HTTPException(500, "whoop-write-api not installed")
    except Exception as e:
        raise HTTPException(401, f"whoop login failed: {e}")

    from datetime import datetime
    existing = db.query(WhoopToken).first()
    if existing:
        existing.access_token = tokens.access_token
        existing.refresh_token = tokens.refresh_token
        existing.expires_at = datetime.fromtimestamp(tokens.expires_at)
    else:
        db.add(WhoopToken(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=datetime.fromtimestamp(tokens.expires_at),
        ))
    db.commit()
    return {"connected": True}
```

- [ ] **Step 8: Run test to verify it passes**

```bash
pytest tests/test_whoop.py::test_cognito_login -v
```

Expected: PASS

- [ ] **Step 9: Remove Whoop env vars from config.py**

Remove `whoop_client_id`, `whoop_client_secret`, `whoop_access_token` from `server/config.py` Settings class (lines 6-8). Whoop availability is now determined by presence of WhoopToken row, not env vars.

- [ ] **Step 10: Update routes that check `settings.whoop_access_token`**

In `server/routes/workout.py` (lines 162-176), replace the settings check with a DB token check:

```python
# old: if settings.whoop_access_token:
# new:
token = db.query(WhoopToken).first()
if token:
    try:
        from server.services.whoop_service import get_whoop_client, push_workout_to_whoop
        result = await push_workout_to_whoop(db, workout.id)
        whoop_synced = result.get("synced", False)
        whoop_error = result.get("error")
    except Exception as e:
        whoop_synced = False
        whoop_error = str(e)
```

In `server/routes/chat.py` (line 28 in `_maybe_trigger_whoop_sync`), replace the settings check similarly.

- [ ] **Step 11: Run full test suite**

```bash
pytest -x --tb=short
```

Expected: All tests pass

- [ ] **Step 12: Commit**

```bash
git add server/services/whoop_service.py server/routes/whoop.py server/config.py server/routes/workout.py server/routes/chat.py tests/test_whoop.py
git commit -m "feat: cognito auth, client factory, remove whoop env vars"
```

---

### Task 6: Comment out OAuth routes (disabled fallback)

**Files:**
- Modify: `server/routes/whoop.py:127-190`
- Modify: `frontend/src/api.ts:31,35`

- [ ] **Step 1: Comment out OAuth routes in whoop.py**

Comment out (don't delete) the following routes:
- `GET /whoop/authorize` (lines 127-140)
- `GET /whoop/callback` (lines 143-190)
- `POST /whoop/test-write` (lines 258-285)

Also comment out the related helpers: `_set_oauth_state`, `_get_oauth_state`, `_get_write_token`, `_set_write_token`.

Remove the `_refresh_token` and `_get_valid_token` functions — token refresh is now handled by the client factory's `on_token_refresh` callback.

Update the `/whoop/sync` route to use `get_whoop_client(db)` instead of the old token-based approach.

Update the `/whoop/status` route: `connected` checks for WhoopToken row, remove `oauth_available` and `write_enabled` (both always true when connected via Cognito).

- [ ] **Step 2: Remove OAuth/test-write from frontend api.ts**

Remove these lines from `frontend/src/api.ts`:
```typescript
// remove:
whoopAuthorize: () => get('/whoop/authorize'),
whoopTestWrite: () => post('/whoop/test-write'),
```

- [ ] **Step 3: Run test suite**

```bash
pytest -x --tb=short
```

Fix any tests that reference removed routes.

- [ ] **Step 4: Commit**

```bash
git add server/routes/whoop.py frontend/src/api.ts tests/test_whoop.py
git commit -m "feat: disable OAuth routes, keep as fallback, remove test-write"
```

---

## PR 3: Tool-Use Loop + Auto-Sync

### Task 7: Implement Claude tool-use loop

**Files:**
- Modify: `server/services/claude_service.py:136-208`
- Create: `tests/test_claude_sdk.py` (add tool-use tests)

This is the P0 infrastructure that enables all Whoop tool interactions.

- [ ] **Step 1: Write failing test for tool-use loop**

```python
# tests/test_claude_sdk.py
@pytest.mark.asyncio
async def test_tool_use_loop_executes_tool():
    """When Claude returns tool_use, server executes and sends result back."""
    # first call: Claude wants to use a tool
    tool_use_response = MagicMock()
    tool_use_response.content = [MagicMock(
        type="tool_use",
        id="call_123",
        name="create_whoop_activity",
        input={"activity_type": "sauna", "duration_minutes": 20}
    )]
    tool_use_response.stop_reason = "tool_use"

    # second call: Claude gives final text response
    final_response = MagicMock()
    final_response.content = [MagicMock(
        type="text",
        text='{"response": "Logged 20-min sauna to Whoop.", "layout": null}'
    )]
    final_response.stop_reason = "end_turn"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            side_effect=[tool_use_response, final_response]
        )

        with patch("server.services.claude_service.execute_whoop_tool") as mock_tool:
            mock_tool.return_value = {"success": True, "activity_id": "uuid-123"}

            from server.services.claude_service import _call_claude_with_tools
            result = await _call_claude_with_tools(
                system_prompt="test",
                message="log a sauna",
                tools=[{"name": "create_whoop_activity", "description": "test", "input_schema": {}}],
                tool_executor=mock_tool,
                db=MagicMock(),
            )

        assert "Logged 20-min sauna" in result
        mock_tool.assert_called_once_with(
            "create_whoop_activity",
            {"activity_type": "sauna", "duration_minutes": 20},
            mock.ANY,  # db
        )
        assert mock_client.messages.create.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_claude_sdk.py::test_tool_use_loop_executes_tool -v
```

Expected: FAIL (`_call_claude_with_tools` doesn't exist yet)

- [ ] **Step 3: Implement `_call_claude_with_tools()`**

Add to `server/services/claude_service.py`:

```python
MAX_TOOL_ITERATIONS = 3
TOOL_TIMEOUT = 30  # seconds

async def _call_claude_with_tools(
    system_prompt: str,
    message: str,
    tools: list[dict],
    tool_executor,
    db,
    history: list[dict] | None = None,
) -> str:
    client = anthropic.AsyncAnthropic()
    messages = history or []
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

        if response.stop_reason != "tool_use":
            # final text response
            text_blocks = [b.text for b in response.content if b.type == "text"]
            raw = " ".join(text_blocks)
            return _extract_json(raw.strip())

        # execute each tool call
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await tool_executor(block.name, block.input, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        messages.append({"role": "user", "content": tool_results})

    # max iterations reached, return last text
    return '{"response": "I had trouble completing that action.", "layout": null}'
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_claude_sdk.py::test_tool_use_loop_executes_tool -v
```

Expected: PASS

- [ ] **Step 5: Write test for max iterations safety**

```python
@pytest.mark.asyncio
async def test_tool_use_loop_respects_max_iterations():
    """Tool loop stops after MAX_TOOL_ITERATIONS."""
    tool_response = MagicMock()
    tool_response.content = [MagicMock(
        type="tool_use", id="call_1", name="test", input={}
    )]
    tool_response.stop_reason = "tool_use"

    with patch("server.services.claude_service.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=tool_response)

        with patch("server.services.claude_service.execute_whoop_tool") as mock_tool:
            mock_tool.return_value = {"ok": True}

            from server.services.claude_service import _call_claude_with_tools
            result = await _call_claude_with_tools(
                "test", "test", [{"name": "test", "description": "t", "input_schema": {}}],
                mock_tool, MagicMock(),
            )

        assert "trouble" in result
        assert mock_client.messages.create.call_count == 3  # MAX_TOOL_ITERATIONS
```

- [ ] **Step 6: Run test**

```bash
pytest tests/test_claude_sdk.py::test_tool_use_loop_respects_max_iterations -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/services/claude_service.py tests/test_claude_sdk.py
git commit -m "feat: claude tool-use loop with max iteration safety"
```

---

### Task 8: Create Whoop tool dispatch

**Files:**
- Create: `server/services/whoop_tools.py`
- Create: `tests/test_whoop_tools.py`

- [ ] **Step 1: Write failing test for tool dispatch**

```python
# tests/test_whoop_tools.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_create_activity_tool():
    with patch("server.services.whoop_tools.get_whoop_client") as mock_factory:
        mock_client = AsyncMock()
        mock_factory.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.create_activity = AsyncMock(return_value=MagicMock(id="uuid-123"))

        from server.services.whoop_tools import execute_whoop_tool
        result = await execute_whoop_tool(
            "create_whoop_activity",
            {"activity_type": "sauna", "duration_minutes": 20},
            MagicMock(),  # db
        )

    assert result["success"] is True
    assert result["activity_id"] == "uuid-123"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    from server.services.whoop_tools import execute_whoop_tool
    result = await execute_whoop_tool("nonexistent_tool", {}, MagicMock())
    assert "error" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_whoop_tools.py -v
```

Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement whoop_tools.py**

```python
# server/services/whoop_tools.py
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def handle_create_activity(params, db):
    from server.services.whoop_service import get_whoop_client
    activity_type = params["activity_type"]
    duration = params.get("duration_minutes", 30)

    if "start_time" in params:
        start = params["start_time"]
    else:
        end = datetime.utcnow()
        start = (end - timedelta(minutes=duration)).isoformat() + "Z"

    end_time = params.get("end_time")
    if not end_time:
        end_time = (datetime.fromisoformat(start.replace("Z", "")) + timedelta(minutes=duration)).isoformat() + "Z"

    async with get_whoop_client(db) as client:
        result = await client.create_activity(activity_type, start=start, end=end_time)
    return {"success": True, "activity_id": result.id}


async def handle_update_weight(params, db):
    from server.services.whoop_service import get_whoop_client
    weight_lbs = params["weight_lbs"]
    weight_kg = weight_lbs / 2.20462
    async with get_whoop_client(db) as client:
        await client.update_weight(weight_kg)
    return {"success": True, "weight_kg": round(weight_kg, 1)}


async def handle_set_alarm(params, db):
    from server.services.whoop_service import get_whoop_client
    async with get_whoop_client(db) as client:
        await client.set_alarm(params["time"], enabled=params.get("enabled", True))
    return {"success": True, "alarm_time": params["time"]}


async def handle_delete_activity(params, db):
    from server.services.whoop_service import get_whoop_client
    activity_id = params["activity_id"]
    is_recovery = params.get("is_recovery", False)
    async with get_whoop_client(db) as client:
        await client.delete_activity(activity_id, is_recovery=is_recovery)
    return {"success": True, "deleted": activity_id}


async def handle_list_activities(params, db):
    from server.services.whoop_service import get_whoop_client
    limit = params.get("limit", 5)
    async with get_whoop_client(db) as client:
        workouts = await client.get_workouts()
    activities = [{"id": w.id, "sport": w.sport_id, "start": str(w.start)} for w in workouts[:limit]]
    return {"success": True, "activities": activities}


async def handle_search_catalog(params, db):
    from server.models import ExerciseCatalog
    query = params["query"].lower()
    results = db.query(ExerciseCatalog).filter(
        ExerciseCatalog.name.ilike(f"%{query}%")
    ).limit(10).all()
    return {
        "success": True,
        "exercises": [{"id": r.whoop_id, "name": r.name, "equipment": r.equipment} for r in results],
    }


TOOL_HANDLERS = {
    "create_whoop_activity": handle_create_activity,
    "update_whoop_weight": handle_update_weight,
    "set_whoop_alarm": handle_set_alarm,
    "delete_whoop_activity": handle_delete_activity,
    "list_whoop_activities": handle_list_activities,
    "search_exercise_catalog": handle_search_catalog,
}


async def execute_whoop_tool(name, params, db):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"unknown tool: {name}"}
    try:
        return await handler(params, db)
    except Exception as e:
        logger.warning(f"whoop tool {name} failed: {e}")
        return {"error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_whoop_tools.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/whoop_tools.py tests/test_whoop_tools.py
git commit -m "feat: whoop tool dispatch — create activity, weight, alarm, delete, catalog"
```

---

### Task 9: Wire tool-use into chat route

**Files:**
- Modify: `server/routes/chat.py:82-227`
- Modify: `server/services/claude_service.py` (update `ClaudeService.chat()`)

- [ ] **Step 1: Define tool schemas**

Add to `server/services/claude_service.py`:

```python
WHOOP_TOOLS = [
    {
        "name": "create_whoop_activity",
        "description": "Log an activity to the user's Whoop. Use for sauna, ice bath, meditation, yoga, stretching, running, cycling, hiking, swimming, walking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "enum": ["sauna", "ice_bath", "meditation", "yoga", "stretching", "running", "cycling", "hiking", "swimming", "walking"]},
                "duration_minutes": {"type": "integer"},
                "start_time": {"type": "string", "description": "ISO 8601 timestamp, optional"},
            },
            "required": ["activity_type", "duration_minutes"],
        },
    },
    {
        "name": "update_whoop_weight",
        "description": "Update body weight on Whoop.",
        "input_schema": {
            "type": "object",
            "properties": {"weight_lbs": {"type": "number"}},
            "required": ["weight_lbs"],
        },
    },
    {
        "name": "set_whoop_alarm",
        "description": "Set or disable Whoop alarm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "time": {"type": "string", "description": "HH:MM format"},
                "enabled": {"type": "boolean"},
            },
            "required": ["time"],
        },
    },
    {
        "name": "delete_whoop_activity",
        "description": "Delete an activity from Whoop. Confirm with user before calling.",
        "input_schema": {
            "type": "object",
            "properties": {"activity_id": {"type": "string"}},
            "required": ["activity_id"],
        },
    },
    {
        "name": "list_whoop_activities",
        "description": "List recent Whoop activities to find an activity ID for deletion or reference.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
        },
    },
    {
        "name": "search_exercise_catalog",
        "description": "Search Whoop exercise catalog by name, equipment, or muscle group. Returns top 10 matches.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]
```

- [ ] **Step 2: Update `ClaudeService.chat()` to use tools when Whoop is connected**

**IMPORTANT:** Keep existing argument order `(message, context)` — add `db` as keyword-only. The existing signature at `claude_service.py:140` is `async def chat(self, message: str, context: str)`. All callers use `service.chat(request.message, context)`.

```python
async def chat(self, message: str, context: str, db=None):
    whoop_connected = db and db.query(WhoopToken).first() is not None if db else False

    if whoop_connected:
        from server.services.whoop_tools import execute_whoop_tool
        raw = await _call_claude_with_tools(
            system_prompt=context,
            message=message,
            tools=WHOOP_TOOLS,
            tool_executor=execute_whoop_tool,
            db=db,
        )
    else:
        raw = await _call_claude(context, message)

    # existing JSON parsing and layout validation...
```

- [ ] **Step 3: Pass `db` through the chat route to ClaudeService**

In `server/routes/chat.py`, update ALL call sites to pass `db`:

```python
# chat route (line 158): already uses (body.message, context)
claude_response = await claude.chat(body.message, context, db=db)

# intake route (line 315): also needs db
claude_response = await claude.chat(message, context, db=db)
```

- [ ] **Step 4: Run test suite**

```bash
pytest -x --tb=short
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add server/services/claude_service.py server/routes/chat.py
git commit -m "feat: wire whoop tools into claude chat when connected"
```

---

### Task 10: Workout auto-sync with exercise mapping

**Files:**
- Modify: `server/services/whoop_service.py:77-116`
- Modify: `server/routes/workout.py:152-177`

- [ ] **Step 1: Write failing test for DetailedExercise sync**

```python
# add to tests/test_whoop.py
@pytest.mark.asyncio
async def test_push_workout_with_detailed_exercises(seeded_db):
    """Workout sync sends DetailedExercise with sets to Whoop."""
    from server.models import Exercise, Set

    # seed exercise with whoop mapping
    ex = seeded_db.query(Exercise).first()
    ex.whoop_exercise_id = "BENCHPRESS_BARBELL"
    seeded_db.commit()

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_client = AsyncMock()
        mock_factory.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_activity = MagicMock()
        mock_activity.id = "activity-uuid"
        mock_client.create_activity = AsyncMock(return_value=mock_activity)
        mock_client.link_exercises_detailed = AsyncMock()

        from server.services.whoop_service import push_workout_to_whoop
        result = await push_workout_to_whoop(seeded_db, 1)

    assert result["synced"] is True
    assert result["activity_id"] == "activity-uuid"
    mock_client.link_exercises_detailed.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_whoop.py::test_push_workout_with_detailed_exercises -v
```

- [ ] **Step 3: Rewrite `push_workout_to_whoop()` for v0.4**

Replace lines 77-116 in `server/services/whoop_service.py`:

```python
async def push_workout_to_whoop(db, workout_id):
    """sync a completed workout to whoop with detailed exercises."""
    try:
        from whoop import DetailedExercise, ExerciseSet
    except ImportError:
        return {"synced": False, "error": "whoop-write-api not installed"}

    workout = db.query(Workout).get(workout_id)
    if not workout:
        return {"synced": False, "error": "workout not found"}

    exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    whoop_exercises = []
    for ex in exercises:
        completed_sets = db.query(Set).filter_by(
            exercise_id=ex.id, completed=True
        ).all()
        if not completed_sets:
            continue
        whoop_exercises.append(DetailedExercise(
            exercise_id=ex.whoop_exercise_id or ex.name.upper().replace(" ", ""),
            name=ex.name,
            sets=[ExerciseSet(reps=s.reps, weight=s.weight) for s in completed_sets],
        ))

    try:
        async with get_whoop_client(db) as client:
            # Workout model has no created_at — derive start from date + duration
            from server.config import TIMEZONE
            end = datetime.now(TIMEZONE)
            duration = 60  # default 60 min if unknown
            start = end - timedelta(minutes=duration)

            activity = await client.create_activity(
                "weightlifting",
                start=start.isoformat(),
                end=end.isoformat(),
            )

            if whoop_exercises:
                await client.link_exercises_detailed(activity.id, whoop_exercises)

            workout.whoop_activity_id = activity.id
            db.commit()
            return {"synced": True, "activity_id": activity.id}
    except Exception as e:
        _queue_failed_sync(db, workout_id, workout.date, e)
        return {"synced": False, "error": str(e), "queued": True}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_whoop.py::test_push_workout_with_detailed_exercises -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/whoop_service.py tests/test_whoop.py
git commit -m "feat: workout auto-sync with DetailedExercise and exercise ID mapping"
```

---

### Task 11: Smart sync triggers

**Files:**
- Modify: `server/services/whoop_service.py:28-74`
- Modify: `server/routes/chat.py:22-47`

- [ ] **Step 1: Write failing test for staleness-based sync**

```python
# add to tests/test_whoop.py
@pytest.mark.asyncio
async def test_sync_skips_when_fresh(db):
    """sync_whoop_biometrics skips if data is less than 2 hours old."""
    from datetime import datetime, timedelta
    from server.models import WhoopData

    db.add(WhoopData(
        date="2026-03-18",
        recovery_score=78.0,
        synced_at=datetime.utcnow() - timedelta(minutes=30),
    ))
    db.commit()

    from server.services.whoop_service import sync_whoop_biometrics
    result = await sync_whoop_biometrics(db, force=False)
    assert result["skipped"] is True
```

- [ ] **Step 2: Run test**

```bash
pytest tests/test_whoop.py::test_sync_skips_when_fresh -v
```

- [ ] **Step 3: Rewrite `sync_whoop_biometrics()` with new signature**

The current function takes `(db, whoop_client)`. Change to `(db, force=False)` — the function creates its own client via `get_whoop_client(db)`. This breaks the existing sync route and all 4 sync tests — we'll fix those in steps 4-5.

```python
import asyncio

_sync_lock = asyncio.Lock()
STALENESS_THRESHOLD = 7200  # 2 hours in seconds

async def sync_whoop_biometrics(db, force=False):
    async with _sync_lock:
        if not force:
            from server.config import today_eastern
            latest = db.query(WhoopData).filter(
                WhoopData.date == today_eastern()
            ).first()
            if latest and latest.synced_at:
                age = (datetime.utcnow() - latest.synced_at).total_seconds()
                if age < STALENESS_THRESHOLD:
                    return {"skipped": True, "reason": "fresh"}

        try:
            async with get_whoop_client(db) as client:
                # existing sync logic: get_recovery, get_sleep, get_cycles
                # but now using client from factory instead of passed-in client
                recovery = await client.get_recovery()
                sleep_data = await client.get_sleep()
                # ... rest of existing sync logic, upsert into WhoopData ...
        except Exception as e:
            return {"synced": False, "error": str(e)}
```

- [ ] **Step 4: Update sync route in whoop.py**

The sync route at `server/routes/whoop.py:225-236` currently calls `sync_whoop_biometrics(db, client)`. Update to:

```python
@router.get("/whoop/sync")
async def whoop_sync(db: Session = Depends(get_db)):
    from server.services.whoop_service import sync_whoop_biometrics
    result = await sync_whoop_biometrics(db, force=True)
    return result
```

Remove the token/client creation from this route — the service handles it now.

- [ ] **Step 5: Update existing sync tests**

All 4 sync tests in `tests/test_whoop.py` pass a mock client as the second arg. Update them to patch `get_whoop_client` instead:

```python
# old pattern (lines 70-101, 104-115, 119-141, 375-396):
# result = await sync_whoop_biometrics(db, mock_client)

# new pattern:
with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
    mock_client = AsyncMock()
    mock_factory.return_value = mock_client
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_recovery = AsyncMock(return_value=[mock_recovery])
    # ... setup mocks ...
    result = await sync_whoop_biometrics(db, force=True)
```

Also update `test_complete_workout_no_whoop` (line 284-308) — it currently patches `settings.whoop_access_token`. Update to check for absence of `WhoopToken` row instead.

- [ ] **Step 6: Run all sync tests**

```bash
pytest tests/test_whoop.py -v -k "sync"
```

Expected: All pass with new mocking pattern

- [ ] **Step 7: Update `_maybe_trigger_whoop_sync()` in chat.py**

Replace lines 22-47 in `server/routes/chat.py` to use the new token-from-DB pattern and call `sync_whoop_biometrics(db, force=False)`:

```python
async def _maybe_trigger_whoop_sync(db):
    """trigger background sync if whoop is connected and data is stale."""
    from server.models import WhoopToken
    token = db.query(WhoopToken).first()
    if not token:
        return
    try:
        from server.services.whoop_service import sync_whoop_biometrics
        asyncio.create_task(sync_whoop_biometrics(db, force=False))
    except Exception:
        pass  # non-blocking, best-effort
```

- [ ] **Step 5: Run tests**

```bash
pytest -x --tb=short
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/services/whoop_service.py server/routes/chat.py tests/test_whoop.py
git commit -m "feat: smart sync with 2-hour staleness threshold and async lock"
```

---

### Task 13: Populate exercise catalog on login

**Files:**
- Modify: `server/routes/whoop.py` (login route)
- Modify: `server/services/whoop_service.py`

- [ ] **Step 1: Write failing test for catalog population**

```python
# add to tests/test_whoop.py
@pytest.mark.asyncio
async def test_populate_exercise_catalog(db):
    """Fetching exercise catalog populates ExerciseCatalog table."""
    from server.models import ExerciseCatalog

    mock_catalog = MagicMock()
    mock_catalog.exercises = [
        MagicMock(id="BENCHPRESS_BARBELL", name="Bench Press", equipment="BARBELL", muscle_group="CHEST"),
        MagicMock(id="SQUAT_BARBELL", name="Squat", equipment="BARBELL", muscle_group="LEGS"),
    ]

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_client = AsyncMock()
        mock_factory.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_exercises = AsyncMock(return_value=mock_catalog)

        from server.services.whoop_service import populate_exercise_catalog
        await populate_exercise_catalog(db)

    assert db.query(ExerciseCatalog).count() == 2
    bench = db.query(ExerciseCatalog).filter_by(whoop_id="BENCHPRESS_BARBELL").first()
    assert bench.name == "Bench Press"
```

- [ ] **Step 2: Implement `populate_exercise_catalog()`**

Add to `server/services/whoop_service.py`:

```python
async def populate_exercise_catalog(db):
    """fetch full exercise catalog from whoop and cache locally."""
    from server.models import ExerciseCatalog

    async with get_whoop_client(db) as client:
        catalog = await client.get_exercises()

    # clear existing and repopulate
    db.query(ExerciseCatalog).delete()
    for ex in catalog.exercises:
        db.add(ExerciseCatalog(
            whoop_id=ex.id, name=ex.name,
            equipment=getattr(ex, 'equipment', None),
            muscle_group=getattr(ex, 'muscle_group', None),
        ))
    db.commit()
```

- [ ] **Step 3: Trigger catalog fetch after successful login**

In the Cognito login route (`server/routes/whoop.py`), after storing tokens:

```python
# after db.commit() in login route:
try:
    from server.services.whoop_service import populate_exercise_catalog
    await populate_exercise_catalog(db)
except Exception:
    pass  # catalog fetch is best-effort, login still succeeds
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_whoop.py -v -k "catalog"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/whoop_service.py server/routes/whoop.py tests/test_whoop.py
git commit -m "feat: populate exercise catalog from whoop on login"
```

---

## PR 4: Coaching + Journal + Frontend

### Task 14: Enhanced coaching rules in system prompt

**Files:**
- Modify: `server/services/claude_service.py:12-74`

- [ ] **Step 1: Expand the system prompt with personalized coaching rules**

Replace the coaching section of `SYSTEM_PROMPT` (lines 55-60 in claude_service.py) with the full rules from the spec (Section 4: Coaching Rules). Include:

- Verbosity scaling (silent on GREEN normal, vocal on RED)
- Signal priority: sleep > HRV trend > recovery > strain
- Personalized thresholds (yellow baseline, sleep debt > hours, protect bench)
- Heavy bench gating rules
- Sauna strain exclusion
- Caffeine timing
- RPE calibration across recovery zones
- User override respect
- Tool behavior rules (execute-then-announce for low risk, confirm for destructive)
- Error language ("Whoop disconnected", never technical terms)

- [ ] **Step 2: Update `assemble_context()` with HRV trend**

Add 7-day HRV average computation to `assemble_context()` (after line 112):

```python
# 7-day HRV trend
from sqlalchemy import func
hrv_avg = db.query(func.avg(WhoopData.hrv)).filter(
    WhoopData.hrv.isnot(None)
).order_by(WhoopData.date.desc()).limit(7).scalar()

if hrv_avg and whoop and whoop.get("hrv"):
    today_hrv = whoop["hrv"]
    hrv_delta = ((today_hrv - hrv_avg) / hrv_avg) * 100
    context_parts.append(f"HRV trend: today {today_hrv}ms vs 7-day avg {hrv_avg:.0f}ms ({hrv_delta:+.0f}%)")
```

Add stale data flag:

```python
from server.config import today_eastern
if whoop and whoop.get("date") != today_eastern():
    context_parts.append("Note: Whoop data is from yesterday, may not reflect current readiness")
```

Add tool/catalog availability flags:

```python
from server.models import WhoopToken, ExerciseCatalog
if db.query(WhoopToken).first():
    context_parts.append("Whoop tools available: you can log activities, update weight, set alarm")
if db.query(ExerciseCatalog).first():
    context_parts.append("Exercise catalog loaded: use search_exercise_catalog to map exercises to Whoop IDs")
```

- [ ] **Step 3: Run tests**

```bash
pytest -x --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add server/services/claude_service.py
git commit -m "feat: enhanced coaching rules with personalized thresholds and HRV trends"
```

---

### Task 15: Meal journal signal extraction

**Files:**
- Modify: `server/routes/chat.py` (meal parsing section)
- Modify: `server/services/whoop_service.py` (add journal sync)

- [ ] **Step 1: Write failing test for journal sync from meals**

```python
# add to tests/test_whoop.py
@pytest.mark.asyncio
async def test_journal_sync_from_meals(db):
    """Journal signals computed from meals and synced to Whoop."""
    from server.models import Meal, WhoopToken
    from datetime import datetime

    db.add(WhoopToken(
        access_token="test", refresh_token="test",
        expires_at=datetime.utcnow(),
    ))
    db.add(Meal(
        date="2026-03-18", description="chicken and coffee",
        calories=500, protein=45,
        journal_signals='{"caffeine": 1, "alcohol": false}',
        created_at=datetime(2026, 3, 18, 12, 0),
    ))
    db.add(Meal(
        date="2026-03-18", description="beer and pizza",
        calories=800, protein=20,
        journal_signals='{"caffeine": 0, "alcohol": true}',
        created_at=datetime(2026, 3, 18, 21, 0),  # late meal
    ))
    db.commit()

    from server.services.whoop_service import compute_journal_state
    state = compute_journal_state(db, "2026-03-18")
    assert state["caffeine"] == 1
    assert state["alcohol"] is True
    assert state["late_meal"] is True
    assert state["protein"] == 65
```

- [ ] **Step 2: Run test**

```bash
pytest tests/test_whoop.py::test_journal_sync_from_meals -v
```

- [ ] **Step 3: Implement `compute_journal_state()`**

Add to `server/services/whoop_service.py`:

```python
import json

def compute_journal_state(db, date_str):
    """compute accumulated journal signals from all meals on a date."""
    meals = db.query(Meal).filter(Meal.date == date_str).all()
    caffeine = 0
    alcohol = False
    late_meal = False
    protein = 0

    for meal in meals:
        if meal.journal_signals:
            signals = json.loads(meal.journal_signals) if isinstance(meal.journal_signals, str) else meal.journal_signals
            caffeine += signals.get("caffeine", 0)
            if signals.get("alcohol", False):
                alcohol = True
        if meal.created_at and meal.created_at.hour >= 20:
            late_meal = True
        protein += meal.protein or 0

    return {"caffeine": caffeine, "alcohol": alcohol, "late_meal": late_meal, "protein": protein}
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_whoop.py::test_journal_sync_from_meals -v
```

Expected: PASS

- [ ] **Step 5: Add journal sync function**

```python
async def sync_journal_to_whoop(db, date_str):
    """sync accumulated journal signals to whoop."""
    try:
        from whoop import JournalInput
    except ImportError:
        return {"synced": False, "error": "whoop-write-api not installed"}

    state = compute_journal_state(db, date_str)
    journal_inputs = []

    if state["caffeine"] > 0:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=2, answered_yes=True,
            magnitude_input_value=state["caffeine"],
        ))
    journal_inputs.append(JournalInput(
        behavior_tracker_id=1, answered_yes=state["alcohol"],
    ))
    if state["late_meal"]:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=6, answered_yes=True,
        ))
    if state["protein"] > 0:
        journal_inputs.append(JournalInput(
            behavior_tracker_id=89, answered_yes=True,
            magnitude_input_value=state["protein"],
        ))

    try:
        async with get_whoop_client(db) as client:
            await client.log_journal(date_str, journal_inputs)
        return {"synced": True}
    except Exception as e:
        _queue_failed_sync(db, None, str(e), sync_type="journal")
        return {"synced": False, "error": str(e), "queued": True}
```

- [ ] **Step 6: Wire journal sync into meal logging in chat.py**

In the meal saving section of `chat.py` (where Claude's meal response is saved), add:

```python
# after saving meal to DB:
if db.query(WhoopToken).first():
    from server.services.whoop_service import sync_journal_to_whoop
    asyncio.create_task(sync_journal_to_whoop(db, today_eastern()))
```

- [ ] **Step 7: Update Claude's system prompt to return journal_signals in meal parse**

Add to the meal parsing instructions in `SYSTEM_PROMPT`:

```
When parsing a meal, also extract journal signals:
- "journal_signals": {"caffeine": <count>, "alcohol": <bool>}
- Count caffeinated drinks (coffee, espresso, latte, tea, energy drink, pre-workout)
- "decaf" = caffeine 0, "coffee with Mike" = caffeine 1
- Flag alcohol (beer, wine, cocktail, spirits, hard seltzer)
- "virgin mojito" = alcohol false
```

- [ ] **Step 8: Run tests**

```bash
pytest -x --tb=short
```

- [ ] **Step 9: Commit**

```bash
git add server/services/whoop_service.py server/routes/chat.py tests/test_whoop.py
git commit -m "feat: meal journal signal extraction and whoop journal sync"
```

---

### Task 16: One-time education messages

**Files:**
- Modify: `server/services/claude_service.py` (context assembly)

- [ ] **Step 1: Add one-time flags to context assembly**

In `assemble_context()`, check SystemMemory for education flags and include instructions for Claude:

```python
from server.models import SystemMemory

def _check_onboarding_flag(db, key):
    row = db.query(SystemMemory).filter_by(key=key).first()
    return row is not None

# in assemble_context():
if whoop_connected and not _check_onboarding_flag(db, "whoop_first_workout_shown"):
    context_parts.append(
        "IMPORTANT: This is the user's first workout with Whoop connected. "
        "Acknowledge it briefly: mention you can see their recovery data and will "
        "factor it into training. Keep it short. After your response, the system "
        "will mark this as shown."
    )
if whoop_connected and not _check_onboarding_flag(db, "whoop_journal_education_shown"):
    context_parts.append(
        "IMPORTANT: On the user's first meal log with Whoop connected, briefly mention "
        "that you're tracking caffeine and alcohol to their Whoop journal. Say you won't "
        "mention it again unless something looks off."
    )
```

- [ ] **Step 2: Mark flags after Claude responds**

In the chat route, after a successful response that included onboarding context:

```python
# after claude response, mark onboarding flags
if whoop_connected:
    for key in ["whoop_first_workout_shown", "whoop_journal_education_shown"]:
        if not db.query(SystemMemory).filter_by(key=key).first():
            # only mark if the response context included the instruction
            if is_workout_context:
                db.add(SystemMemory(key="whoop_first_workout_shown", content="true"))
            if is_meal_context:
                db.add(SystemMemory(key="whoop_journal_education_shown", content="true"))
    db.commit()
```

- [ ] **Step 3: Run tests**

```bash
pytest -x --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add server/services/claude_service.py server/routes/chat.py
git commit -m "feat: one-time education messages for whoop journal and first workout"
```

---

### Task 17: Frontend — Profile screen and ContextBanner

**Files:**
- Modify: `frontend/src/screens/profile.tsx`
- Modify: `frontend/src/components/context-banner.tsx`
- Modify: `frontend/src/components/day-card.tsx`

- [ ] **Step 1: Simplify Profile screen to single Cognito login**

In `profile.tsx`:
- Remove the `handleConnect()` function (OAuth redirect — lines 73-87)
- Remove the `handleTestWrite()` function (lines 122-137)
- Remove the OAuth connect button and test-write button from JSX
- Remove `oauthAvailable` and `writeEnabled` state
- Update `whoopStatus()` response handling: just check `connected` boolean
- Add value prop text above login form when disconnected
- Add password reassurance below form
- Make stats section collapsible (collapsed by default)
- Add migration note if needed (check for SystemMemory `whoop_migration_shown`)

- [ ] **Step 2: Add stale/disconnected states to ContextBanner**

In `context-banner.tsx`:
- Check if recovery data date matches today
- If stale: show `GREEN 78% (yesterday)` label
- If no recovery data and no Whoop token: show nothing (existing behavior)
- If Whoop was connected but auth expired (check `/whoop/status`): show `Whoop disconnected` with tap handler to navigate to Profile tab

```typescript
// add to ContextBanner
const isStale = recovery && recovery.date !== todayDate;
const isDisconnected = whoopStatus?.needs_attention;

// in JSX:
{isDisconnected ? (
  <span onClick={() => onNavigate?.('profile')} style={{cursor: 'pointer'}}>
    Whoop disconnected
  </span>
) : recovery ? (
  <span>
    {recovery.zone} {recovery.score}%
    {isStale && ' (yesterday)'}
  </span>
) : null}
```

- [ ] **Step 3: Add failure-only sync indicator to DayCard**

In `day-card.tsx`, add optional `whoopSyncStatus` prop:

```typescript
// only show on failure/pending
{whoopSyncStatus === 'pending' && <span>Whoop sync pending</span>}
{whoopSyncStatus === 'failed' && <span>Sync failed</span>}
```

- [ ] **Step 4: Build frontend**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: profile cognito login, context banner stale/disconnected states"
```

---

### Task 18: Final integration test and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full backend test suite**

```bash
pytest -x --tb=short
```

Expected: All tests pass

- [ ] **Step 2: Build frontend**

```bash
cd frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 3: Start dev server and smoke test**

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Manual smoke tests:
- Open PWA, verify ContextBanner loads
- Go to Profile, verify Cognito login form shows
- Chat with Claude, verify response returns
- If Whoop connected: verify sync triggers, recovery shows in banner

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

- [ ] **Step 5: Update CLAUDE.md if needed**

If any architecture descriptions in `CLAUDE.md` are now outdated (e.g., the Whoop section describing OAuth), update them to reflect Cognito auth and the new tool-use architecture.

- [ ] **Step 6: Commit CLAUDE.md**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for whoop v0.4 architecture"
```
