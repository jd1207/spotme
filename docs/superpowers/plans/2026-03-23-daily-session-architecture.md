# Daily Session Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-message CLI subprocess spawning with a single daily session that persists conversation state, streams responses, and handles tool-use in 2 calls.

**Architecture:** Claude CLI sessions (`--session-id`, `--resume`) provide conversation continuity without persistent processes. One session per day, stored as a UUID in the DB. Daily handoff summarizes the old session into a TrainingLog entry before replacing it. Streaming uses `--output-format stream-json --verbose`, piped as SSE to the frontend.

**Tech Stack:** Python/FastAPI (backend), Claude CLI 2.1.81 (`--print`, `--resume`, `--session-id`, `--output-format stream-json`), React 19/TypeScript (frontend SSE consumer)

**Spec:** `docs/superpowers/specs/2026-03-23-daily-session-architecture-design.md`

---

## Task 1: Session Manager — create and resume daily sessions

**Files:**
- Create: `server/services/session_manager.py`
- Modify: `server/config.py:21-22`
- Test: `tests/test_session_manager.py`

This is the core new module. It manages session lifecycle: create, resume, handoff, recover.

- [ ] **Step 1: Add rollover config**

In `server/config.py`, add after line 22:

```python
SESSION_ROLLOVER_HOUR = 4
```

- [ ] **Step 2: Write failing tests for session manager**

Create `tests/test_session_manager.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base
from server.models import SystemMemory
from server.services.session_manager import SessionManager

def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def test_get_session_creates_new_when_none_exists():
    db = _make_db()
    mgr = SessionManager()
    session_id = mgr.get_or_create_session_id(db, "2026-03-23")
    assert session_id is not None
    # stored in DB
    row = db.query(SystemMemory).filter_by(key="active_session").first()
    assert row is not None
    data = json.loads(row.content)
    assert data["session_id"] == session_id
    assert data["date"] == "2026-03-23"

def test_get_session_reuses_existing_same_day():
    db = _make_db()
    mgr = SessionManager()
    id1 = mgr.get_or_create_session_id(db, "2026-03-23")
    id2 = mgr.get_or_create_session_id(db, "2026-03-23")
    assert id1 == id2

def test_get_session_creates_new_on_new_day():
    db = _make_db()
    mgr = SessionManager()
    old_id = mgr.get_or_create_session_id(db, "2026-03-22")
    new_id = mgr.get_or_create_session_id(db, "2026-03-23")
    assert old_id != new_id
    row = db.query(SystemMemory).filter_by(key="active_session").first()
    data = json.loads(row.content)
    assert data["date"] == "2026-03-23"

def test_is_first_message_of_day():
    db = _make_db()
    mgr = SessionManager()
    assert mgr.is_first_message(db, "2026-03-23") is True
    mgr.get_or_create_session_id(db, "2026-03-23")
    assert mgr.is_first_message(db, "2026-03-23") is False

def test_needs_handoff():
    db = _make_db()
    mgr = SessionManager()
    mgr.get_or_create_session_id(db, "2026-03-22")
    assert mgr.needs_handoff(db, "2026-03-23") is True
    assert mgr.needs_handoff(db, "2026-03-22") is False

def test_invalidate_session():
    db = _make_db()
    mgr = SessionManager()
    mgr.get_or_create_session_id(db, "2026-03-23")
    mgr.invalidate_session(db)
    assert mgr.is_first_message(db, "2026-03-23") is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_session_manager.py -v`
Expected: FAIL (module doesn't exist yet)

- [ ] **Step 4: Implement session manager**

Create `server/services/session_manager.py`:

```python
import json
import logging
import os
import uuid

from server.models import SystemMemory

logger = logging.getLogger(__name__)

SESSION_KEY = "active_session"
SESSIONS_DIR = os.path.expanduser("~/.claude/projects/-home-deck-spotme")


class SessionManager:

    def get_or_create_session_id(self, db, today: str) -> str:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if row and row.content:
            data = json.loads(row.content)
            if data.get("date") == today:
                return data["session_id"]
            # new day — delete old session file, create new
            self._delete_session_file(data.get("session_id"))

        new_id = str(uuid.uuid4())
        payload = json.dumps({"session_id": new_id, "date": today})
        if row:
            row.content = payload
        else:
            db.add(SystemMemory(key=SESSION_KEY, content=payload))
        db.commit()
        return new_id

    def is_first_message(self, db, today: str) -> bool:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return True
        data = json.loads(row.content)
        return data.get("date") != today

    def needs_handoff(self, db, today: str) -> bool:
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return False
        data = json.loads(row.content)
        return data.get("date") != today and data.get("session_id") is not None

    def get_old_session(self, db) -> tuple[str | None, str | None]:
        """return (session_id, date) of the old session, or (None, None)"""
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if not row or not row.content:
            return None, None
        data = json.loads(row.content)
        return data.get("session_id"), data.get("date")

    def invalidate_session(self, db):
        row = db.query(SystemMemory).filter_by(key=SESSION_KEY).first()
        if row:
            if row.content:
                data = json.loads(row.content)
                self._delete_session_file(data.get("session_id"))
            db.delete(row)
            db.commit()

    def _delete_session_file(self, session_id: str | None):
        if not session_id:
            return
        path = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
        try:
            os.remove(path)
            logger.info("deleted session file: %s", path)
        except FileNotFoundError:
            pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_session_manager.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add server/services/session_manager.py tests/test_session_manager.py server/config.py
git commit -m "feat: add session manager for daily Claude CLI sessions"
```

---

## Task 2: Session-aware Claude calls — replace `_call_claude` for chat

**Files:**
- Modify: `server/services/claude_service.py:396-468`
- Test: `tests/test_session_calls.py`

Replace `_call_claude()` (used by chat) with session-aware versions. Keep the old `_call_claude()` renamed to `_call_claude_stateless()` for interview/form analysis.

- [ ] **Step 1: Write failing tests**

Create `tests/test_session_calls.py`:

```python
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from server.services.claude_service import (
    _call_claude_session,
    _call_claude_stateless,
    _session_lock,
)

@pytest.fixture
def mock_subprocess():
    """mock asyncio.create_subprocess_exec to return a fake process"""
    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(
        json.dumps({"response": "test reply"}).encode(),
        b"",
    ))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc

@pytest.mark.asyncio
async def test_session_call_uses_resume(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        result = await _call_claude_session(
            session_id="abc-123",
            message="hello",
            is_first=False,
        )
        args = mock_exec.call_args[0]
        assert "--resume" in args
        assert "abc-123" in args
        assert "--session-id" not in args

@pytest.mark.asyncio
async def test_session_call_uses_session_id_for_first(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        result = await _call_claude_session(
            session_id="abc-123",
            message="hello",
            is_first=True,
            system_prompt="you are a coach",
        )
        args = mock_exec.call_args[0]
        assert "--session-id" in args
        assert "abc-123" in args
        assert "--append-system-prompt" in args

@pytest.mark.asyncio
async def test_stateless_call_uses_no_session_persistence(mock_subprocess):
    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_exec:
        result = await _call_claude_stateless("system", "message")
        args = mock_exec.call_args[0]
        assert "--no-session-persistence" in args
        assert "--resume" not in args

@pytest.mark.asyncio
async def test_session_lock_prevents_concurrent_calls(mock_subprocess):
    """two calls should serialize, not run in parallel"""
    call_order = []

    async def slow_communicate():
        call_order.append("start")
        await asyncio.sleep(0.1)
        call_order.append("end")
        return (json.dumps({"response": "ok"}).encode(), b"")

    mock_subprocess.communicate = slow_communicate

    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess):
        await asyncio.gather(
            _call_claude_session("id", "msg1", is_first=False),
            _call_claude_session("id", "msg2", is_first=False),
        )

    # should be start,end,start,end (serial) not start,start,end,end (parallel)
    assert call_order == ["start", "end", "start", "end"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_calls.py -v`
Expected: FAIL (functions don't exist yet)

- [ ] **Step 3: Implement session-aware call functions**

In `server/services/claude_service.py`, replace the `_call_claude` function (lines 396-417) and `_call_claude_with_tools` function (lines 420-468) with:

```python
_session_lock = asyncio.Lock()


async def _call_claude_session(
    session_id: str,
    message: str,
    is_first: bool = False,
    system_prompt: str | None = None,
) -> str:
    """call claude within a persistent daily session."""
    async with _session_lock:
        args = [CLAUDE_BIN, "--print", "--tools", ""]
        if is_first:
            args.extend(["--session-id", session_id, "--model", MODEL])
            if system_prompt:
                args.extend(["--append-system-prompt", system_prompt])
        else:
            args.extend(["--resume", session_id])
        args.extend(["-p", message])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("claude cli timed out after 120s")
        if proc.returncode != 0:
            error = stderr.decode().strip()
            logger.error("claude session error: %s", error)
            raise RuntimeError(f"claude cli failed: {error}")
        raw = stdout.decode().strip()
        return _extract_json(raw)


async def _call_claude_stateless(system_prompt: str, message: str) -> str:
    """call claude without session persistence (for one-off calls like interview questions)."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--no-session-persistence",
        "--model", MODEL,
        "--tools", "",
        "--append-system-prompt", system_prompt,
        "-p", message,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("claude cli timed out after 120s")
    if proc.returncode != 0:
        error = stderr.decode().strip()
        logger.error("claude cli error: %s", error)
        raise RuntimeError(f"claude cli failed: {error}")
    raw = stdout.decode().strip()
    return _extract_json(raw)
```

Also update `generate_interview_questions` (line 348) and `analyze_form` (line 375) to call `_call_claude_stateless` instead of `_call_claude`.

Remove the old `_call_claude` function (lines 396-417) and `_call_claude_with_tools` function (lines 420-468), and `MAX_TOOL_ITERATIONS` (line 420).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_calls.py tests/test_claude_sdk.py -v`
Expected: session tests PASS. Existing claude tests may need updating for renamed function.

- [ ] **Step 5: Fix broken existing tests**

In `tests/test_claude_sdk.py`:
- Rename all `_call_claude` imports/references to `_call_claude_stateless`
- Delete the `test_tool_use_loop_executes_tool` test (and any other `_call_claude_with_tools` tests) — tool-use is now handled by the 2-call session pattern in `ClaudeService.chat()`
- Verify: `pytest tests/test_claude_sdk.py -v` passes

- [ ] **Step 6: Commit**

```bash
git add server/services/claude_service.py tests/test_session_calls.py tests/test_claude_sdk.py
git commit -m "feat: add session-aware and stateless Claude CLI call functions"
```

---

## Task 3: Rewrite chat route to use sessions + 2-call tool pattern

**Files:**
- Modify: `server/routes/chat.py:82-280`
- Modify: `server/services/claude_service.py` (ClaudeService.chat method, lines 298-335)
- Test: `tests/test_chat_session.py`

The chat route now: gets/creates the daily session, sends the message via `_call_claude_session`, handles tool-use with a follow-up `--resume` call, and processes side effects.

- [ ] **Step 1: Write failing test for session-based chat**

Create `tests/test_chat_session.py`:

```python
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.models import SystemMemory, UserProfile, Conversation
from server.config import today_eastern

def _make_app():
    from server.main import create_app
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    def override():
        db = TestSession()
        try: yield db
        finally: db.close()
    app = create_app()
    app.dependency_overrides[get_db] = override
    return TestClient(app), TestSession

def test_chat_creates_session_on_first_message():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.commit()
    db.close()

    mock_response = json.dumps({"response": "Hey! Ready to train.", "layout": None})
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/api/chat", json={"message": "hi", "workout_id": None, "date": None})
    assert resp.status_code == 200

    db = TestSession()
    session_row = db.query(SystemMemory).filter_by(key="active_session").first()
    assert session_row is not None
    data = json.loads(session_row.content)
    assert data["date"] == today_eastern()
    db.close()

def test_chat_resumes_existing_session():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.add(SystemMemory(key="active_session", content=json.dumps({"session_id": "existing-uuid", "date": today_eastern()})))
    db.commit()
    db.close()

    mock_response = json.dumps({"response": "Welcome back.", "layout": None})
    with patch("server.services.claude_service._call_claude_session", new_callable=AsyncMock, return_value=mock_response) as mock_call:
        resp = client.post("/api/chat", json={"message": "hey", "workout_id": None, "date": None})
    assert resp.status_code == 200
    # should have used resume (is_first=False)
    _, kwargs = mock_call.call_args
    assert kwargs.get("is_first") is False
    assert kwargs.get("session_id") == "existing-uuid"

def test_chat_tool_calls_execute_and_followup():
    client, TestSession = _make_app()
    db = TestSession()
    db.add(UserProfile(name="Test"))
    db.add(SystemMemory(key="active_session", content=json.dumps({"session_id": "tool-uuid", "date": today_eastern()})))
    # seed a WhoopToken so the tool-use path is triggered
    from server.models import WhoopToken
    db.add(WhoopToken(access_token="fake", refresh_token="fake", user_id="1"))
    db.commit()
    db.close()

    # first call returns tool_calls, second returns final response
    call_count = 0
    async def mock_session_call(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return json.dumps({"response": "Logging your sauna.", "tool_calls": [{"name": "create_whoop_activity", "arguments": {"activity_type": "sauna", "duration_minutes": 20}}]})
        return json.dumps({"response": "Done — 20 min sauna logged."})

    with patch("server.services.claude_service._call_claude_session", side_effect=mock_session_call):
        with patch("server.services.whoop_tools.execute_whoop_tool", new_callable=AsyncMock, return_value={"success": True}):
            resp = client.post("/api/chat", json={"message": "log my 20 min sauna", "workout_id": None, "date": None})

    assert resp.status_code == 200
    assert call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_session.py -v`
Expected: FAIL

- [ ] **Step 3: Rewrite ClaudeService.chat() to use sessions**

In `server/services/claude_service.py`, replace the `ClaudeService.chat()` method (lines 298-335) with:

```python
class ClaudeService:

    def __init__(self):
        from server.services.session_manager import SessionManager
        self.session_mgr = SessionManager()

    async def chat(self, message: str, context: str, db=None, date: str | None = None) -> dict:
        from server.config import today_eastern
        today = date or today_eastern()

        is_first = self.session_mgr.is_first_message(db, today)

        # daily handoff: summarize old session before creating new
        if self.session_mgr.needs_handoff(db, today):
            await self._do_handoff(db, today)

        session_id = self.session_mgr.get_or_create_session_id(db, today)

        try:
            if is_first:
                # first message: system prompt in --append-system-prompt, context + user msg in -p
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=f"Current context:\n{context}\n\n{message}",
                    is_first=True,
                    system_prompt=SYSTEM_PROMPT,
                )
            else:
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=message,
                    is_first=False,
                )
        except Exception as e:
            logger.error("claude session call failed: %s", e)
            # try recovery: invalidate and retry as fresh session
            self.session_mgr.invalidate_session(db)
            try:
                session_id = self.session_mgr.get_or_create_session_id(db, today)
                full_message = f"{context}\n\n{message}"
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=full_message,
                    is_first=True,
                    system_prompt=system,
                )
            except Exception as e2:
                logger.error("claude recovery failed: %s", e2)
                return self._error_response()

        # parse response
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None, "profile": None, "memory_update": None, "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None}

        # handle tool calls — 2nd call within the same session
        tool_calls = parsed.get("tool_calls", [])
        if tool_calls and db:
            from server.services.whoop_tools import execute_whoop_tool
            results = []
            for tc in tool_calls:
                result = await execute_whoop_tool(tc["name"], tc.get("arguments", {}), db)
                results.append({"tool": tc["name"], "result": result})
            # follow-up in same session with tool results
            try:
                followup_text = await _call_claude_session(
                    session_id=session_id,
                    message=f"Tool results: {json.dumps(results)}",
                    is_first=False,
                )
                try:
                    parsed = json.loads(followup_text)
                except json.JSONDecodeError:
                    parsed["response"] = followup_text

            except Exception:
                # tool followup failed — use the initial response
                pass

        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None

        return {
            "response": parsed.get("response", raw_text),
            "layout": layout,
            "profile": parsed.get("profile"),
            "memory_update": parsed.get("memory_update"),
            "training_log_entry": parsed.get("training_log_entry"),
            "set_suggestion": parsed.get("set_suggestion"),
            "meal": parsed.get("meal"),
            "workout_plan": parsed.get("workout_plan"),
        }

    _handoff_lock = asyncio.Lock()

    async def _do_handoff(self, db, today: str):
        """summarize old session and create new one"""
        async with self._handoff_lock:
            if not self.session_mgr.needs_handoff(db, today):
                return  # another concurrent call already did it
            old_id, old_date = self.session_mgr.get_old_session(db)
            if not old_id:
                return
            try:
                summary_text = await _call_claude_session(
                    session_id=old_id,
                    message="Summarize today's coaching session in 2-3 sentences. Include: what was trained, key performance notes, any program adjustments discussed, and anything to carry forward to tomorrow.",
                    is_first=False,
                )
                # extract the response text from JSON (not the raw JSON blob)
                try:
                    parsed = json.loads(summary_text)
                    summary_content = parsed.get("response", summary_text)
                except json.JSONDecodeError:
                    summary_content = summary_text
                from server.models import TrainingLog
                db.add(TrainingLog(
                    date=old_date or today,
                    log_type="daily_summary",
                    content=summary_content[:500],
                ))
                db.commit()
            except Exception as e:
                logger.warning("session handoff summary failed: %s", e)
            # invalidate old session (deletes file)
            self.session_mgr.invalidate_session(db)

    def _error_response(self):
        return {"response": "Having trouble reaching Claude right now. Try again in a sec.", "layout": None, "profile": None, "memory_update": None, "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None}
```

- [ ] **Step 4: Update chat route to pass `date` to service**

In `server/routes/chat.py` line 171, change:
```python
result = await service.chat(request.message, context, db=db)
```
to:
```python
result = await service.chat(request.message, context, db=db, date=request_date)
```

- [ ] **Step 5: Unblock concurrent memory_update + training_log_entry**

In `server/routes/chat.py` line 198, change:
```python
if memory_update and isinstance(memory_update, str) and not log_entry:
```
to:
```python
if memory_update and isinstance(memory_update, str):
    # safety: reject if update is >50% shorter (accidental truncation)
    if memory_row and len(memory_update) < len(memory_row.content or "") * 0.5:
        logger.warning("blocked memory_update: %d chars vs existing %d chars", len(memory_update), len(memory_row.content or ""))
    elif memory_row:
```
Preserve the existing `else` branch for creating new memory.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_chat_session.py tests/test_chat.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/services/claude_service.py server/routes/chat.py tests/test_chat_session.py
git commit -m "feat: rewrite chat to use daily session with 2-call tool pattern"
```

---

## Task 4: Frontend streaming — receive SSE and render tokens incrementally

**Files:**
- Modify: `frontend/src/api.ts:17`
- Modify: `frontend/src/screens/workout.tsx:86-105`
- Create: `server/routes/chat_stream.py`
- Modify: `server/main.py` (register new router)

- [ ] **Step 1: Create SSE streaming endpoint**

Create `server/routes/chat_stream.py`:

```python
import asyncio
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from server.database import get_db
from server.services.claude_service import CLAUDE_BIN, MODEL, SYSTEM_PROMPT, _session_lock, _extract_json, assemble_context
from server.services.session_manager import SessionManager
from server.models import SystemMemory, Conversation, UserProfile, WhoopData, Meal, Workout, Exercise, Set
from server.config import today_eastern
from sqlalchemy import func as sqlfunc

logger = logging.getLogger(__name__)
router = APIRouter()
session_mgr = SessionManager()

from server.schemas import ChatRequest

@router.post("/chat/stream")
async def stream_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """SSE endpoint that streams Claude's response token by token"""
    message = request.message
    request_date = request.date or today_eastern()

    # build context (same as chat route)
    profile = db.query(UserProfile).first()
    profile_dict = {"name": profile.name, "goals": profile.goals, "experience_level": profile.experience_level, "equipment": profile.equipment, "training_frequency": profile.training_frequency, "injuries_notes": profile.injuries_notes, "calorie_target": profile.calorie_target, "protein_target": profile.protein_target} if profile else None
    whoop_dict = None
    whoop = db.query(WhoopData).filter_by(date=today_eastern()).first()
    if whoop:
        whoop_dict = {"recovery_score": whoop.recovery_score, "hrv": whoop.hrv, "resting_hr": whoop.resting_hr, "sleep_score": whoop.sleep_score, "sleep_duration": whoop.sleep_duration, "strain": whoop.strain}
    memory_row = db.query(SystemMemory).filter_by(key="training_plan").first()
    memory_text = memory_row.content if memory_row else None
    from server.models import TrainingLog
    recent_logs = db.query(TrainingLog).order_by(TrainingLog.id.desc()).limit(15).all()
    training_log_dicts = [{"date": log.date, "type": log.log_type, "content": log.content} for log in reversed(recent_logs)]
    context = assemble_context(None, None, whoop_dict, [], profile_dict, memory_text, training_log=training_log_dicts, db=db)

    is_first = session_mgr.is_first_message(db, request_date)
    if session_mgr.needs_handoff(db, request_date):
        from server.services.claude_service import ClaudeService
        svc = ClaudeService()
        await svc._do_handoff(db, request_date)

    session_id = session_mgr.get_or_create_session_id(db, request_date)
    system = f"{SYSTEM_PROMPT}\n\nCurrent context:\n{context}"

    args = [CLAUDE_BIN, "--print", "--output-format", "stream-json", "--verbose", "--tools", ""]
    if is_first:
        args.extend(["--session-id", session_id, "--model", MODEL, "--append-system-prompt", system])
        msg = f"{context}\n\n{message}"
    else:
        args.extend(["--resume", session_id])
        msg = message
    args.extend(["-p", msg])

    async def event_stream():
        # acquire lock only to start the process, then release
        async with _session_lock:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        # stream outside the lock — session file is safe once the process has started
        full_text = ""
        try:
            async for line in proc.stdout:
                decoded = line.decode().strip()
                if not decoded:
                    continue
                try:
                    event = json.loads(decoded)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "assistant":
                    content = event.get("message", {}).get("content", [])
                    for block in content:
                        if block.get("type") == "text":
                            text = block["text"]
                            full_text += text
                            yield f"data: {json.dumps({'text': text})}\n\n"
            await proc.wait()
        except Exception as e:
            logger.error("stream error: %s", e)
            proc.kill()
            await proc.wait()

        # save conversation
        db.add(Conversation(role="user", content=message, context_type="chat", date=request_date))
        db.add(Conversation(role="assistant", content=full_text, context_type="chat", date=request_date))
        db.commit()

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 2: Register the streaming router in main.py**

In `server/main.py`, add:
```python
from server.routes.chat_stream import router as chat_stream_router
app.include_router(chat_stream_router, prefix="/api")
```

- [ ] **Step 3: Add `chatStream()` to frontend API**

In `frontend/src/api.ts`, add after the `chat` method:

```typescript
chatStream: async (message: string, date?: string, onToken?: (text: string) => void): Promise<string> => {
  const resp = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, workout_id: null, date: date ?? null }),
  })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let full = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    for (const line of chunk.split('\n')) {
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6))
        if (data.done) return full
        if (data.text) {
          full += data.text
          onToken?.(full)
        }
      } catch {}
    }
  }
  return full
},
```

- [ ] **Step 4: Update `send()` in workout.tsx to use streaming**

In `frontend/src/screens/workout.tsx`, replace the `send` function (lines 86-105):

```typescript
const send = async (text: string) => {
  if (!text.trim()) return
  setMessages(m => [...m, { role: 'user', content: text }])
  setInput('')
  setThinking(true)
  try {
    const wid = workoutId && workoutId > 0 ? workoutId : undefined
    if (wid) {
      // active workout: use non-streaming (needs workout_id context)
      const result = await api.chat(text, wid, wid ? undefined : chatDate)
      setMessages(m => [...m, { role: 'assistant', content: result.response }])
      if (result.workout_active && result.current_set) {
        setWorkoutId(result.workout_id ?? null)
        setCurrentSet(result.current_set)
        setSetProgress({ completed: 0, total: 0, current_exercise_progress: '0 of 0' })
      }
    } else {
      // daily chat: use streaming
      setMessages(m => [...m, { role: 'assistant', content: '' }])
      setThinking(false)
      await api.chatStream(text, chatDate, (partial) => {
        setMessages(m => {
          const updated = [...m]
          updated[updated.length - 1] = { role: 'assistant', content: partial }
          return updated
        })
      })
    }
  } catch {
    // recovery: try to load from server history
    if (document.hidden) {
      await new Promise<void>(resolve => {
        const handler = () => { if (!document.hidden) { document.removeEventListener('visibilitychange', handler); resolve() } }
        document.addEventListener('visibilitychange', handler)
      })
    }
    try {
      const history = await api.getChatDay(chatDate)
      const msgs = history.messages.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }))
      if (msgs.length > 0) { setMessages(msgs); return }
    } catch {}
    setMessages(m => [...m, { role: 'assistant', content: 'Connection error — try again in a sec.' }])
  } finally {
    setThinking(false)
  }
}
```

- [ ] **Step 5: Build and type-check frontend**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add server/routes/chat_stream.py server/main.py frontend/src/api.ts frontend/src/screens/workout.tsx
git commit -m "feat: add SSE streaming for chat responses"
```

---

## Task 5: Cleanup — stale sessions, dead code, stale args

**Files:**
- Modify: `server/routes/video.py:20`
- Modify: `server/routes/layout.py:19`
- Run: cleanup script

- [ ] **Step 1: Fix stale `api_key` arguments**

In `server/routes/video.py` line 20, change:
```python
claude = ClaudeService(api_key=settings.anthropic_api_key)
```
to:
```python
claude = ClaudeService()
```

In `server/routes/layout.py` line 17-19, change:
```python
    if settings.anthropic_api_key:
        try:
            service = ClaudeService(api_key=settings.anthropic_api_key)
```
to:
```python
    try:
        service = ClaudeService()
```
(Remove the `if settings.anthropic_api_key:` guard — ClaudeService now uses CLI OAuth, not an API key.)

- [ ] **Step 2: Delete stale session files**

```bash
rm -f ~/.claude/projects/-home-deck-spotme/*.jsonl
echo "deleted $(ls ~/.claude/projects/-home-deck-spotme/*.jsonl 2>/dev/null | wc -l) stale sessions"
```

- [ ] **Step 3: Run full test suite**

Run: `pytest -x --tb=short`
Expected: all tests PASS

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: clean build

- [ ] **Step 5: Commit**

```bash
git add server/routes/video.py server/routes/layout.py
git commit -m "fix: remove stale api_key args, clean up session files"
```

---

## Task 6: Integration verification

**Files:** None (testing only)

- [ ] **Step 1: Restart service**

```bash
systemctl --user restart spotme
```

- [ ] **Step 2: Verify session creation**

```bash
# send a test message via curl
curl -s -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "hey", "workout_id": null, "date": null}' | python3 -m json.tool | head -5
```

Verify: only 1 session file in `~/.claude/projects/-home-deck-spotme/`

- [ ] **Step 3: Verify session resumption**

Send a second message and verify it reuses the same session:

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "what did I just say?", "workout_id": null, "date": null}' | python3 -m json.tool | head -5
```

Expected: Claude references the prior message. Still only 1 session file.

- [ ] **Step 4: Verify streaming endpoint**

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello", "workout_id": null, "date": null}' 2>&1 | head -10
```

Expected: SSE events with `data: {"text": "..."}` lines.

- [ ] **Step 5: Verify disk usage**

```bash
ls ~/.claude/projects/-home-deck-spotme/*.jsonl | wc -l
du -sh ~/.claude/projects/-home-deck-spotme/
```

Expected: 1 file, <1MB
