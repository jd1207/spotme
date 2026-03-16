# SpotMe

AI-powered workout tracker. Claude coaches, Whoop provides biometrics, PWA runs on phone.

## Architecture

```
Phone (PWA) <---> FastAPI (Steam Deck :8000) <---> Claude API
                        |
                        +--> Whoop API (read biometrics, write workouts)
                        +--> SQLite (spotme.db)
```

## Commands

```bash
# backend
pip install -e ".[dev]"
pytest -x --tb=short                          # run tests
uvicorn server.main:app --host 0.0.0.0 --port 8000  # dev server

# frontend
cd frontend && npm install && npm run build   # build PWA
cd frontend && npm run dev                    # dev server with HMR

# deploy
systemctl --user restart spotme               # restart server
journalctl --user -u spotme -f                # tail logs
```

## Directory Layout

- `server/` — Python FastAPI backend
  - `routes/` — API endpoints (all prefixed `/api`)
  - `services/` — business logic (claude, whoop, video, layout)
  - `models.py` — SQLAlchemy ORM models
  - `schemas.py` — Pydantic request/response DTOs
- `frontend/src/` — React TypeScript PWA
  - `components/` — 10 layout-driven UI components
  - `screens/` — 5 full-page views
  - `hooks/` — voice, camera, offline
- `tests/` — pytest suite
- `deploy/` — systemd service files

## Unstable Dependency: whoop-write-api

The Whoop write API uses reverse-engineered endpoints that can break without notice.

**Rules:**
- always lazy-import whoop inside functions, never at module top level
- always wrap whoop calls in try/except with graceful degradation
- queue failed syncs to `WhoopSyncQueue` with error details for retry
- the app must work 100% without whoop — it's a nice-to-have, not a dependency
- when whoop endpoints change, update whoop-write-api repo first, then bump here
- test whoop integration with mocks by default; real API calls only in manual testing

## Claude API Integration

- use `anthropic.AsyncAnthropic` (async only)
- model: `claude-sonnet-4-20250514` (defined in `claude_service.py`)
- system prompt + context assembled server-side via `assemble_context()`
- claude responses with layouts must pass through `validate_layout()` before reaching frontend
- invalid JSON from claude falls back to raw text with `layout: None`
- send last 5 messages of history, not full conversation
- keep context under ~4000 tokens per request

## Dynamic Layout System

Claude returns JSON layout descriptors. Only these component types are valid:
`header`, `stat_card`, `exercise_card`, `set_logger`, `rest_timer`,
`text_block`, `video_prompt`, `chart`, `action_button`, `chat_bubble`

Unknown types are silently dropped. Invalid layouts fall back to cached version.

## Database

- SQLAlchemy 2.x with sync `Session` (not async engine)
- hierarchy: Program > Workout > Exercise > Set
- dates as ISO strings (`YYYY-MM-DD`), weight in lbs (float), reps int, RPE float 0-10
- workout status: `active` -> `completed`
- use `get_db()` dependency injection for all route handlers
- tests use `sqlite:///:memory:` with `StaticPool`

## Testing

- mock claude API in all tests — never make real API calls
- mock whoop API by default
- use FastAPI `dependency_overrides[get_db]` for route tests
- use today's date when seeding test workouts (route queries `date.today()`)

## Deployment (Steam Deck)

- runs as systemd user service, not root
- steam deck has read-only rootfs — all installs to `~/.local/bin`
- whoop sync fires daily at 07:00 via systemd timer
- accessible from gym via Tailscale
- ffmpeg is a runtime dependency for video frame extraction

## Security

- never commit `.env` or API keys
- all secrets loaded from env vars via `server/config.py`
- no app-level auth — Tailscale is the auth boundary
