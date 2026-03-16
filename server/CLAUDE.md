# SpotMe Backend

Python 3.11+ FastAPI with SQLAlchemy + SQLite. All routes under `/api` prefix.

## Patterns

- async route handlers (`async def`)
- `Depends(get_db)` for database sessions in all routes
- services handle business logic, routes handle HTTP
- pydantic schemas in `schemas.py` for all request/response types
- config loaded from `.env` via `pydantic_settings.BaseSettings`

## Whoop Integration

whoop-write-api is an unstable reverse-engineered dependency:

```python
# correct: lazy import inside function, wrapped in try/except
async def sync_whoop(db):
    try:
        from whoop import WhoopClient
        client = WhoopClient(token=settings.whoop_access_token)
        # ... do work
    except (ImportError, Exception) as e:
        return {"error": str(e)}

# wrong: top-level import
from whoop import WhoopClient  # breaks if lib not installed or API changed
```

Failed syncs go to `WhoopSyncQueue` table for retry. The app must never crash
or lose functionality because Whoop is down or the API changed.

## Claude API

- `ClaudeService` wraps `anthropic.AsyncAnthropic`
- `assemble_context()` builds context string from program + workout + whoop + history
- all claude responses with layouts pass through `validate_layout()`
- system prompt requests JSON with `response` and `layout` fields
- model currently `claude-sonnet-4-20250514` — change in one place only

## Adding a New Route

1. create `server/routes/new_route.py` with `router = APIRouter()`
2. add request/response schemas to `schemas.py`
3. register in `server/main.py`: `app.include_router(router, prefix="/api")`
4. add tests in `tests/test_new_route.py`
