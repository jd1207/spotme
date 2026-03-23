# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Framework

**Runner:**
- pytest 9.0.2 with pytest-asyncio 1.3.0
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- Python 3.13.1

**Assertion Library:**
- Built-in `assert` statements (pytest rewrites)
- No additional assertion library

**Run Commands:**
```bash
cd /home/deck/spotme
.venv/bin/python -m pytest tests/ -x --tb=short   # run all, stop on first failure
.venv/bin/python -m pytest tests/test_chat.py -v   # single file
.venv/bin/python -m pytest tests/ -v               # verbose all
```

**Configuration:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
`asyncio_mode = "auto"` means async test functions are automatically detected -- no need for `@pytest.mark.asyncio` decorator, though it is still used throughout.

## Test File Organization

**Location:** Separate `tests/` directory at project root (not co-located with source).

**Naming:** `test_{module}.py` where module maps to source:
| Test File | Tests For |
|-----------|-----------|
| `tests/test_chat.py` | `server/services/claude_service.py` (assemble_context, ClaudeService.chat) + `server/routes/chat.py` helpers |
| `tests/test_claude_sdk.py` | `server/services/claude_service.py` (_call_claude subprocess, _call_claude_with_tools) |
| `tests/test_daily_chat.py` | `server/routes/chat.py` (daily chat day-scoped endpoints) |
| `tests/test_training_log.py` | TrainingLog model, context assembly, chat route log entry saving |
| `tests/test_layout.py` | `server/services/layout_service.py` (validate_layout) |
| `tests/test_workout.py` | `server/routes/workout.py` (today, next, recent, exercise/last) |
| `tests/test_complete_set.py` | `server/routes/workout.py` (complete-set endpoint) |
| `tests/test_sequencer.py` | `server/services/workout_sequencer.py` (create_workout_from_plan, complete_set, get_next_set) |
| `tests/test_whoop.py` | `server/services/whoop_service.py` (sync_biometrics, push_workout, queue, catalog) |
| `tests/test_whoop_tools.py` | `server/services/whoop_tools.py` (execute_whoop_tool dispatch) |
| `tests/test_morning.py` | `server/routes/morning.py` (morning briefing endpoint) |
| `tests/test_program.py` | `server/routes/program.py` + `server/services/program_parser.py` |
| `tests/test_program_week.py` | `server/routes/program.py` (/program/week endpoint) |
| `tests/test_progress.py` | `server/routes/progress.py` (e1rm, volume, whoop trends) |
| `tests/test_meals.py` | `server/routes/meals.py` (CRUD, totals) |
| `tests/test_meals_day.py` | `server/routes/meals.py` (day-specific endpoint) |
| `tests/test_history_prs.py` | `server/routes/workout.py` (recent) + `server/routes/progress.py` (PRs) |
| `tests/test_database.py` | `server/models.py` (ORM model creation) |
| `tests/test_video.py` | `server/services/video_service.py` (validation, ffmpeg command) |
| `tests/test_utils.py` | `server/config.py` (today_eastern) + `server/utils.py` (recovery_zone) |

**Test count:** 140 tests, all passing.

**Structure:**
```
tests/
├── __init__.py              # empty
├── test_chat.py             # 18 tests (186 lines)
├── test_claude_sdk.py       #  4 tests (94 lines)
├── test_complete_set.py     #  4 tests (110 lines)
├── test_daily_chat.py       #  7 tests (100 lines)
├── test_database.py         #  4 tests (48 lines)
├── test_history_prs.py      #  4 tests (128 lines)
├── test_layout.py           #  5 tests (39 lines)
├── test_meals.py            #  7 tests (117 lines)
├── test_meals_day.py        #  4 tests (65 lines)
├── test_morning.py          #  6 tests (126 lines)
├── test_program.py          #  6 tests (197 lines)
├── test_program_week.py     #  8 tests (192 lines)
├── test_progress.py         #  5 tests (191 lines)
├── test_sequencer.py        #  8 tests (135 lines)
├── test_training_log.py     #  4 tests (141 lines)
├── test_utils.py            #  6 tests (41 lines)
├── test_video.py            #  4 tests (20 lines)
├── test_whoop.py            # 18 tests (575 lines)
└── test_whoop_tools.py      #  4 tests (70 lines)
```

## Database Fixture Patterns

**Primary pattern -- in-memory SQLite with StaticPool:**
```python
@pytest.fixture
def db():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()
```
Used in: `test_chat.py`, `test_sequencer.py`, `test_meals.py`, `test_meals_day.py`, `test_whoop.py`

**Route test pattern -- FastAPI TestClient with dependency override:**
```python
@pytest.fixture
def client(db):
    from server.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
```
Used in: `test_daily_chat.py`, `test_meals.py`, `test_meals_day.py`

**Alternative route pattern -- _make_app_and_session factory:**
```python
def _make_app_and_session():
    from server.main import create_app
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    return app, TestSession
```
Used in: `test_morning.py`, `test_workout.py`, `test_program.py`, `test_program_week.py`, `test_progress.py`, `test_history_prs.py`, `test_complete_set.py`

**Seeded fixture pattern:**
```python
@pytest.fixture
def seeded_db(db):
    program = Program(name="Test", goal="test", phase="test")
    db.add(program)
    db.commit()
    workout = Workout(program_id=program.id, ...)
    db.add(workout)
    db.commit()
    # ... more seed data
    return db
```
Used in: `test_whoop.py` for push_workout tests

## Mocking Claude (Subprocess)

**Pattern 1 -- Mock `_call_claude` at function level:**
The most common pattern mocks the internal `_call_claude` function, bypassing the subprocess entirely. This tests `ClaudeService.chat()` JSON parsing and field extraction.

```python
# tests/test_chat.py
@pytest.mark.asyncio
async def test_chat_returns_text_and_layout():
    with patch("server.services.claude_service._call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = '{"response": "Go heavy today", "layout": {"screen": "workout_session", "layout": [{"type": "header", "title": "Bench Day"}]}}'
        service = ClaudeService()
        result = await service.chat("what's my workout?", context="test context")
        assert "Go heavy" in result["response"]
        assert result["layout"]["screen"] == "workout_session"
```

**Pattern 2 -- Mock subprocess at asyncio level:**
Tests `_call_claude` itself by mocking `asyncio.create_subprocess_exec` and `asyncio.wait_for`. This verifies CLI invocation, JSON extraction, and error handling.

```python
# tests/test_claude_sdk.py
async def _mock_wait_for(coro, timeout):
    """await the coroutine like real wait_for does."""
    return await coro

@pytest.mark.asyncio
async def test_call_claude_returns_json_response():
    from server.services.claude_service import _call_claude
    proc = AsyncMock()
    proc.communicate.return_value = (b'{"response": "test reply", "layout": null}', b"")
    proc.returncode = 0
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            result = await _call_claude("test system prompt", "hello")
    assert "test reply" in result
```

**Pattern 3 -- Mock `ClaudeService` at route level:**
For integration tests of the chat route, the entire `ClaudeService` class is mocked to control the full response dict.

```python
# tests/test_training_log.py
def test_chat_saves_training_log_entry(test_app, engine):
    with patch("server.routes.chat.ClaudeService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.chat = AsyncMock(return_value={
            "response": "Nice work on pull day!",
            "layout": None, "profile": None,
            "memory_update": None, "set_suggestion": None,
            "meal": None, "workout_plan": None,
            "training_log_entry": {
                "type": "completion",
                "day": "Pull / Back",
                "summary": "75 min, all exercises completed",
            },
        })
        resp = test_app.post("/api/chat", json={"message": "just finished pull day"})
    assert resp.status_code == 200
```

## Mocking Whoop

**Pattern -- Mock `get_whoop_client` factory:**
```python
# tests/test_whoop.py
@pytest.mark.asyncio
async def test_sync_biometrics_happy_path(db):
    mock_recovery = MagicMock()
    mock_recovery.created_at = "2026-03-16T10:00:00Z"
    mock_recovery.recovery_score = 85.0
    mock_recovery.hrv = 72.5
    mock_recovery.resting_hr = 50

    mock_client = AsyncMock()
    mock_client.get_recovery.return_value = [mock_recovery]
    mock_client.get_sleep.return_value = [mock_sleep]
    mock_client.get_cycles.return_value = [mock_cycle]

    with patch("server.services.whoop_service.get_whoop_client") as mock_factory:
        mock_factory.return_value = mock_client
        result = await sync_whoop_biometrics(db, force=True)

    assert result["synced"] == 1
```

**What to mock:**
- Always mock `get_whoop_client` -- never call real Whoop API
- Always mock `_call_claude` or `ClaudeService` -- never call real Claude
- Mock `asyncio.create_subprocess_exec` when testing subprocess invocation

**What NOT to mock:**
- SQLAlchemy in-memory database (use real queries against `:memory:`)
- `assemble_context()` (test directly with real arguments)
- `validate_layout()` (pure function, test directly)
- `create_workout_from_plan()` (test with real DB)
- `program_parser.parse_program()` (pure function, test directly)

## Test Data Patterns

**Inline test data:**
```python
# tests/test_program.py
SAMPLE_PLAN = """## Weekly Schedule
- Friday: Pull / Back
- Saturday: Legs
- Sunday: Heavy Bench
### Week 1 (Current)
- Heavy (Sun 3/16): 255x3, 265x4, 225x6x3. COMPLETED on 56% recovery
"""
```

**Workout seeding helper:**
```python
# tests/test_complete_set.py
def _seed_workout(session):
    w = Workout(date=today_eastern(), type="strength", status="active")
    session.add(w)
    session.flush()
    ex = Exercise(workout_id=w.id, name="Bench Press", order=0)
    session.add(ex)
    session.flush()
    sets = []
    for i in range(3):
        s = Set(exercise_id=ex.id, weight=225, reps=5, ...)
        session.add(s)
        session.flush()
        sets.append(s.id)
    session.commit()
    return w.id, sets
```

**No shared fixtures file.** Each test file defines its own fixtures. This leads to fixture duplication (db fixture repeated in 8+ files).

## Coverage

**Requirements:** No coverage threshold enforced. No coverage tool configured in `pyproject.toml`.

**View Coverage:**
```bash
.venv/bin/python -m pytest tests/ --cov=server --cov-report=term-missing
```
(Requires `pytest-cov` to be installed -- not currently in dev dependencies.)

## Test Types

**Unit Tests:**
- Pure function tests: `test_layout.py`, `test_utils.py`, `test_video.py`
- Service method tests with mocked externals: `test_chat.py` (assemble_context), `test_sequencer.py`
- Subprocess mocking tests: `test_claude_sdk.py`

**Integration Tests:**
- Route endpoint tests via FastAPI `TestClient`: `test_daily_chat.py`, `test_workout.py`, `test_meals.py`, `test_morning.py`, `test_program.py`, `test_progress.py`, `test_complete_set.py`, `test_history_prs.py`
- Database integration tests: `test_database.py`
- Whoop service tests with mocked client: `test_whoop.py`

**E2E Tests:**
- Not used. No end-to-end test framework.

**No test for:**
- `server/routes/interview.py` (no `test_interview.py`)
- `server/routes/profile.py` (no `test_profile.py`)
- `server/services/notification_service.py` (no tests)
- `server/cli.py` (no tests)
- `server/main.py` middleware and SPA fallback (no tests)
- `server/scripts/morning_briefing.py` (no tests)
- Error paths in `_call_claude`: timeout killing process, `_extract_json` edge cases

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result["key"] == expected
```
Note: `@pytest.mark.asyncio` is used even though `asyncio_mode = "auto"` makes it redundant.

**Error Testing:**
```python
@pytest.mark.asyncio
async def test_call_claude_raises_on_cli_error():
    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"auth failed")
    proc.returncode = 1
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.wait_for", side_effect=_mock_wait_for):
            with pytest.raises(RuntimeError, match="claude cli failed"):
                await _call_claude("sys", "msg")
```

**Route error testing:**
```python
def test_complete_nonexistent_set():
    client, _ = _make_app()
    resp = client.post("/api/workout/complete-set", json={
        "set_id": 9999, "actual_weight": 225, "actual_reps": 5,
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
```

**Date-sensitive tests:**
Tests that involve "today" queries use `today_eastern()` or `date.today().isoformat()` to seed data for the current date. This ensures queries that filter by today's date match correctly.

## Test Suite Technical Debt

**Duplicated db fixtures:**
The `db` fixture (in-memory SQLite + StaticPool) is copy-pasted in at least 8 test files. Should be extracted to `tests/conftest.py`.

**Duplicated `_make_app_and_session` factory:**
The app factory helper is copy-pasted in 7 test files. Should be a shared fixture.

**Inconsistent fixture patterns:**
Two approaches coexist for route tests:
1. `lambda: db` override (simpler, used in `test_meals.py`, `test_daily_chat.py`)
2. `_make_app_and_session()` with generator override (more correct for session lifecycle)

The `lambda: db` approach does not properly close sessions per-request, which could leak state between tests.

**Missing test coverage for key areas:**
- `server/routes/interview.py` -- no tests at all
- `server/routes/profile.py` -- no tests at all
- Chat route integration (the `/api/chat` endpoint with ClaudeService mock) -- only tested in `test_training_log.py` for specific fields
- Claude timeout handling and process kill path
- `_extract_json()` function edge cases
- `generate_interview_questions()` in `ClaudeService`
- `analyze_form()` in `ClaudeService`
- Memory update guard (blocking memory_update when training_log_entry present) only has 1 test

**No conftest.py:**
`tests/conftest.py` does not exist. All fixtures are local to each test file, causing significant duplication.

**No coverage enforcement:**
`pytest-cov` is not in dev dependencies. No coverage thresholds configured.

---

*Testing analysis: 2026-03-23*
