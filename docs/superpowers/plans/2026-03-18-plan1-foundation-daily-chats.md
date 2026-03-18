# Plan 1: Foundation + Daily Chats

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Eastern timezone helpers, database migrations for new columns, shared utilities, and day-by-day persistent chat with history — the foundation all other features depend on.

**Architecture:** Add `today_eastern()` to config.py and replace all `date.today()` calls. Add `date` column to Conversation, new columns to Set and Meal models. Create chat/days and chat/day/{date} endpoints. Restructure the Workout tab frontend into a daily-chat-first view with history cards.

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-18-daily-chat-workout-diet-overhaul-design.md`

**Test command:** `.venv/bin/python -m pytest -x --tb=short`

**Frontend build:** `cd frontend && npm run build`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `server/config.py` | Modify | Add `TIMEZONE` constant and `today_eastern()` helper |
| `server/utils.py` | Create | Shared `recovery_zone()` utility extracted from morning.py |
| `server/models.py` | Modify | Add `date` to Conversation, `target_weight`/`target_reps`/`set_type`/`order`/`status` to Set, `items` to Meal |
| `server/main.py` | Modify | Add ALTER TABLE migrations for all new columns |
| `server/schemas.py` | Modify | Add `date` field to `ChatRequest` |
| `server/routes/morning.py` | Modify | Use `today_eastern()`, import `recovery_zone` from utils |
| `server/routes/workout.py` | Modify | Replace `date.today()` with `today_eastern()` |
| `server/routes/meals.py` | Modify | Replace `date.today()` with `today_eastern()` |
| `server/routes/chat.py` | Modify | Replace `date.today()`, add date to messages, scope history by date, add `GET /chat/days` and `GET /chat/day/{date}` endpoints |
| `tests/test_utils.py` | Create | Tests for `recovery_zone()` and `today_eastern()` |
| `tests/test_daily_chat.py` | Create | Tests for day-scoped chat endpoints |
| `frontend/src/api.ts` | Modify | Add `getChatDays()`, `getChatDay(date)` API methods |
| `frontend/src/screens/workout.tsx` | Modify | Restructure to show daily chat by default with day history |
| `frontend/src/screens/workout-home.tsx` | Modify | Replace with day-list view when navigating back from chat |
| `frontend/src/components/context-banner.tsx` | Create | Recovery + workout + nutrition context card for chat header |
| `frontend/src/components/day-card.tsx` | Create | Day history card (workout type, recovery dot, stats) |
| `frontend/src/index.css` | Modify | Add styles for context banner, day cards, chat restructure |

---

## Task 1: Timezone Helper + Shared Utils

**Files:**
- Modify: `server/config.py`
- Create: `server/utils.py`
- Modify: `server/routes/morning.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write tests for timezone helper and recovery_zone**

```python
# tests/test_utils.py
import pytest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo


def test_today_eastern_returns_eastern_date():
    from server.config import today_eastern, TIMEZONE
    result = today_eastern()
    expected = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    assert result == expected


def test_today_eastern_format():
    from server.config import today_eastern
    result = today_eastern()
    # YYYY-MM-DD format
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"


def test_recovery_zone_green():
    from server.utils import recovery_zone
    assert recovery_zone(85.0) == "GREEN"
    assert recovery_zone(67.0) == "GREEN"


def test_recovery_zone_yellow():
    from server.utils import recovery_zone
    assert recovery_zone(66.0) == "YELLOW"
    assert recovery_zone(34.0) == "YELLOW"


def test_recovery_zone_red():
    from server.utils import recovery_zone
    assert recovery_zone(33.0) == "RED"
    assert recovery_zone(0.0) == "RED"


def test_recovery_zone_none():
    from server.utils import recovery_zone
    assert recovery_zone(None) == "UNKNOWN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_utils.py -v`
Expected: FAIL — `server/utils.py` doesn't exist, `today_eastern` not in config

- [ ] **Step 3: Implement timezone helper in config.py**

Add to `server/config.py` after the `settings` line:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")


def today_eastern() -> str:
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")
```

- [ ] **Step 4: Create server/utils.py with recovery_zone**

```python
RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34


def recovery_zone(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= RECOVERY_GREEN:
        return "GREEN"
    if score >= RECOVERY_YELLOW:
        return "YELLOW"
    return "RED"
```

- [ ] **Step 5: Update morning.py to use shared utils**

In `server/routes/morning.py`:
- Remove `RECOVERY_GREEN = 67` and `RECOVERY_YELLOW = 34` constants (lines 11-12)
- Remove the `_recovery_zone` function (lines 56-63)
- Add import: `from server.utils import recovery_zone`
- Replace `_recovery_zone(recovery)` call on line 27 with `recovery_zone(recovery)`
- Replace `from datetime import date` with `from server.config import today_eastern`
- Replace `today = date.today()` on line 20 with `today_str = today_eastern()` and `from datetime import datetime` + `today = datetime.now(TIMEZONE).date()` for the `strftime` calls (day_name/day_abbrev still need a date object)

Actually, simpler — morning.py needs both the string and the date object. Keep it as:
```python
from datetime import datetime
from server.config import TIMEZONE, today_eastern

# in morning_briefing:
now = datetime.now(TIMEZONE)
today_str = now.strftime("%Y-%m-%d")
day_name = now.strftime("%A")
day_abbrev = now.strftime("%a")
```

Replace `date.today().isoformat()` on line 25 with `today_str`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_utils.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Run full test suite to verify no regressions**

Run: `.venv/bin/python -m pytest -x --tb=short`
Expected: All 85+ tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/config.py server/utils.py server/routes/morning.py tests/test_utils.py
git commit -m "feat: add timezone helper and shared recovery_zone utility"
```

---

## Task 2: Replace date.today() Across All Routes

**Files:**
- Modify: `server/routes/workout.py`
- Modify: `server/routes/meals.py`
- Modify: `server/routes/chat.py`

- [ ] **Step 1: Update workout.py**

In `server/routes/workout.py`, replace all `date.today().isoformat()` with `today_eastern()`:

- Line 1: Add `from server.config import today_eastern`
- Line 14: `today = today_eastern()` (remove `from datetime import date`)
- Line 39-47: Replace `today = date.today()` with:
  ```python
  from datetime import datetime
  from server.config import TIMEZONE
  now = datetime.now(TIMEZONE)
  day_name = now.strftime("%A")
  day_abbrev = now.strftime("%a")
  ```
- Line 96: `today = today_eastern()` (remove `from datetime import date`)
- Line 112: `today = today_eastern()` (remove `from datetime import date`)

- [ ] **Step 2: Update meals.py**

In `server/routes/meals.py`:

Replace the imports at the top of `meals.py` with:
```python
from datetime import datetime, timedelta
from server.config import TIMEZONE, today_eastern
```

Then replace each `date.today()` call:
- In `log_meal()`: change `data.get("date", date.today().isoformat())` → `data.get("date", today_eastern())`
- In `get_today_meals()`: change `today = date.today().isoformat()` → `today = today_eastern()`
- In `get_week_meals()`: replace the date computation with:
  ```python
  today = datetime.now(TIMEZONE).date()
  week_ago = (today - timedelta(days=6)).isoformat()
  ```

- [ ] **Step 3: Update chat.py date references**

In `server/routes/chat.py`:

- Replace `from datetime import date` import with `from server.config import today_eastern`
- In `_get_today_whoop()`: replace `date.today().isoformat()` with `today_eastern()`
- In `chat()` function, the meal_totals query: replace `.filter(Meal.date == date.today().isoformat())` with `.filter(Meal.date == today_eastern())`
- In `chat()`, the Meal auto-save block: replace `date=date.today().isoformat()` with `date=request_date` (see Task 4 for `request_date` introduction)
- Conversation saves get `date=request_date` in Task 4

**Important:** Use content matching (search for `date.today()`) rather than line numbers, as line numbers shift as the file is edited.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest -x --tb=short`
Expected: All tests PASS. Some test dates use `date.today().isoformat()` in test data — these still work because the Steam Deck is in Eastern time and tests run instantly.

- [ ] **Step 5: Commit**

```bash
git add server/routes/workout.py server/routes/meals.py server/routes/chat.py
git commit -m "refactor: replace date.today() with today_eastern() across all routes"
```

---

## Task 3: Database Migrations — New Columns

**Files:**
- Modify: `server/models.py`
- Modify: `server/main.py`

- [ ] **Step 1: Add new columns to models**

In `server/models.py`:

Add to `Conversation` class (after `context_type`, before `created_at`):
```python
date = Column(String, nullable=True)
```

Add to `Set` class (after `notes`):
```python
target_weight = Column(Float, nullable=True)
target_reps = Column(Integer, nullable=True)
set_type = Column(String, nullable=True)
order = Column(Integer, nullable=True)
status = Column(String, nullable=True)
```

Add to `Meal` class (after `meal_type`, before `created_at`):
```python
items = Column(Text, nullable=True)
```

- [ ] **Step 2: Add migrations to main.py**

In `server/main.py`, extend the existing migration block (after the `protein_target` migration):

```python
# conversation date column
conv_cols = [c['name'] for c in sa_inspect(engine).get_columns('conversations')]
with engine.begin() as conn:
    if 'date' not in conv_cols:
        conn.execute(text("ALTER TABLE conversations ADD COLUMN date TEXT"))

# set columns for workout sequencing
set_cols = [c['name'] for c in sa_inspect(engine).get_columns('sets')]
with engine.begin() as conn:
    if 'target_weight' not in set_cols:
        conn.execute(text("ALTER TABLE sets ADD COLUMN target_weight REAL"))
    if 'target_reps' not in set_cols:
        conn.execute(text("ALTER TABLE sets ADD COLUMN target_reps INTEGER"))
    if 'set_type' not in set_cols:
        conn.execute(text("ALTER TABLE sets ADD COLUMN set_type TEXT"))
    if 'order' not in set_cols:
        conn.execute(text('ALTER TABLE sets ADD COLUMN "order" INTEGER'))
    if 'status' not in set_cols:
        conn.execute(text("ALTER TABLE sets ADD COLUMN status TEXT"))

# meal items column
meal_cols = [c['name'] for c in sa_inspect(engine).get_columns('meals')]
with engine.begin() as conn:
    if 'items' not in meal_cols:
        conn.execute(text("ALTER TABLE meals ADD COLUMN items TEXT"))

# backfill conversation dates from created_at
with engine.begin() as conn:
    conn.execute(text("""
        UPDATE conversations SET date = substr(created_at, 1, 10)
        WHERE date IS NULL AND created_at IS NOT NULL
    """))
```

Note: `order` is a reserved word in SQL — quote it in the ALTER TABLE statement.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest -x --tb=short`
Expected: All tests PASS (new columns are nullable, existing tests unaffected)

- [ ] **Step 4: Commit**

```bash
git add server/models.py server/main.py
git commit -m "feat: add date to Conversation, sequencing cols to Set, items to Meal"
```

---

## Task 4: Chat Day Endpoints (Backend)

**Files:**
- Modify: `server/routes/chat.py`
- Modify: `server/schemas.py`
- Create: `tests/test_daily_chat.py`

- [ ] **Step 1: Write tests for day endpoints**

```python
# tests/test_daily_chat.py
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from server.database import Base, get_db
from server.config import today_eastern
from server.models import Conversation, Workout, WhoopData, Meal


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    from server.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _yesterday() -> str:
    from datetime import datetime
    from server.config import TIMEZONE
    return (datetime.now(TIMEZONE).date() - timedelta(days=1)).isoformat()


def test_chat_days_empty(client):
    resp = client.get("/api/chat/days")
    assert resp.status_code == 200
    assert resp.json()["days"] == []


def test_chat_days_with_messages(db, client):
    today = today_eastern()
    db.add(Conversation(role="user", content="hello", date=today))
    db.add(Conversation(role="assistant", content="hi", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert len(days) == 1
    assert days[0]["date"] == today
    assert days[0]["message_count"] == 2


def test_chat_days_multiple_dates(db, client):
    today = today_eastern()
    yesterday = _yesterday()
    db.add(Conversation(role="user", content="msg1", date=today))
    db.add(Conversation(role="user", content="msg2", date=yesterday))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert len(days) == 2
    assert days[0]["date"] == today  # most recent first


def test_chat_days_includes_workout_type(db, client):
    today = today_eastern()
    db.add(Workout(date=today, type="strength", status="active"))
    db.add(Conversation(role="user", content="hello", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert days[0]["workout_type"] == "strength"


def test_chat_days_includes_recovery(db, client):
    today = today_eastern()
    db.add(WhoopData(date=today, recovery_score=79.0, hrv=65.0, resting_hr=55))
    db.add(Conversation(role="user", content="hello", date=today))
    db.commit()
    resp = client.get("/api/chat/days")
    days = resp.json()["days"]
    assert days[0]["recovery_score"] == 79.0
    assert days[0]["recovery_zone"] == "GREEN"


def test_chat_day_returns_messages(db, client):
    today = today_eastern()
    db.add(Conversation(role="user", content="first", date=today))
    db.add(Conversation(role="assistant", content="second", date=today))
    db.commit()
    resp = client.get(f"/api/chat/day/{today}")
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["content"] == "first"
    assert messages[1]["content"] == "second"


def test_chat_day_empty_date(client):
    resp = client.get("/api/chat/day/2020-01-01")
    assert resp.json()["messages"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_daily_chat.py -v`
Expected: FAIL — endpoints don't exist

- [ ] **Step 3: Update ChatRequest schema**

In `server/schemas.py`, modify `ChatRequest`:
```python
class ChatRequest(BaseModel):
    message: str
    workout_id: int | None = None
    date: str | None = None
```

- [ ] **Step 4: Add chat/days and chat/day/{date} endpoints**

In `server/routes/chat.py`, add these two new endpoints:

```python
from server.utils import recovery_zone
from server.config import today_eastern
from sqlalchemy import func as sqlfunc

@router.get("/chat/days")
async def get_chat_days(db: Session = Depends(get_db)):
    """return list of dates with chat history and summary stats"""
    date_counts = (
        db.query(Conversation.date, sqlfunc.count(Conversation.id).label("count"))
        .filter(Conversation.date.isnot(None))
        .group_by(Conversation.date)
        .order_by(Conversation.date.desc())
        .limit(30)
        .all()
    )
    days = []
    for row in date_counts:
        d = row.date
        workout = db.query(Workout).filter_by(date=d).first()
        whoop = db.query(WhoopData).filter_by(date=d).first()
        meal_totals = db.query(sqlfunc.sum(Meal.calories)).filter(Meal.date == d).scalar()
        # build summary string
        summary_parts = []
        if workout:
            summary_parts.append(workout.type)
        if meal_totals:
            summary_parts.append(f"{meal_totals} cal")
        summary = " · ".join(summary_parts) if summary_parts else "No activity"

        days.append({
            "date": d,
            "message_count": row.count,
            "workout_type": workout.type if workout else None,
            "recovery_score": whoop.recovery_score if whoop else None,
            "recovery_zone": recovery_zone(whoop.recovery_score) if whoop else None,
            "calories_total": meal_totals or 0,
            "summary": summary,
        })
    return {"days": days}


@router.get("/chat/day/{chat_date}")
async def get_chat_day(chat_date: str, db: Session = Depends(get_db)):
    """return all messages for a specific date"""
    messages = (
        db.query(Conversation)
        .filter_by(date=chat_date)
        .order_by(Conversation.created_at)
        .all()
    )
    return {
        "messages": [
            {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
            for m in messages
        ]
    }
```

Also add the required imports at the top: `from server.models import ... Meal` (add Meal to existing import) and `from server.utils import recovery_zone`.

- [ ] **Step 5: Update POST /api/chat to save date on messages and scope history by date**

In the `chat()` function in `server/routes/chat.py`:

**5a.** At the top of the function, add date resolution:
```python
request_date = request.date or today_eastern()
```

**5b.** Replace the history query block (the section starting with `# conversation history scoped to this workout`) with:
```python
# conversation history scoped to this date
history_query = (
    db.query(Conversation)
    .filter_by(date=request_date)
    .order_by(Conversation.created_at.desc())
)
history = history_query.limit(10).all()
history_dicts = [{"role": h.role, "content": h.content} for h in reversed(history)]
```

**5c. IMPORTANT: Preserve the workout_context block.** The section starting with `# current workout context if scoped` must remain unchanged — it reads `request.workout_id` for context assembly and is independent of history filtering.

**5d.** Update the Meal auto-save in the `# auto-save meal if claude estimated macros` block to use `request_date`:
```python
db.add(Meal(
    date=request_date,  # was date.today().isoformat()
    ...
))
```
This ensures meals logged through historical-day chat are dated to that day, not today.

**5e.** Update both Conversation saves (search for `db.add(Conversation(role="user"` and `db.add(Conversation(role="assistant"`) to include `date=request_date`:
```python
db.add(Conversation(role="user", content=request.message, context_type="chat", workout_id=request.workout_id, date=request_date))
db.add(Conversation(role="assistant", content=result["response"], context_type="chat", workout_id=request.workout_id, date=request_date))
```

**5f.** Add retrospective note for historical chats. After the `context = assemble_context(...)` call:
```python
today = today_eastern()
if request_date != today:
    context += f"\n\nNote: athlete is reviewing {request_date} on {today}."
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/test_daily_chat.py -v`
Expected: All 8 tests PASS

- [ ] **Step 7: Run full suite**

Run: `.venv/bin/python -m pytest -x --tb=short`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/routes/chat.py server/schemas.py tests/test_daily_chat.py
git commit -m "feat: add day-scoped chat endpoints and date-based history"
```

---

## Task 5: Frontend — Context Banner Component

**Files:**
- Create: `frontend/src/components/context-banner.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create context-banner.tsx**

```typescript
// frontend/src/components/context-banner.tsx
import { useState, useEffect } from 'react'
import { api } from '../api'

interface ContextBannerProps {
  date: string
}

export function ContextBanner({ date }: ContextBannerProps) {
  const [recovery, setRecovery] = useState<{ score: number; zone: string } | null>(null)
  const [workoutType, setWorkoutType] = useState<string | null>(null)
  const [nutrition, setNutrition] = useState<{ current: number; target: number | null } | null>(null)

  useEffect(() => {
    api.getChatDays().then(r => {
      const day = r.days.find((d: any) => d.date === date)
      if (day) {
        if (day.recovery_score) setRecovery({ score: day.recovery_score, zone: day.recovery_zone })
        if (day.workout_type) setWorkoutType(day.workout_type)
        setNutrition({ current: day.calories_total, target: null })
      }
    }).catch(() => {})
    api.getProfile().then(p => {
      if (p?.calorie_target) {
        setNutrition(prev => prev ? { ...prev, target: p.calorie_target } : null)
      }
    }).catch(() => {})
  }, [date])

  const hasData = recovery || workoutType || (nutrition && nutrition.current > 0)
  if (!hasData) return null

  const zoneColor = recovery?.zone === 'GREEN' ? 'var(--success)' : recovery?.zone === 'YELLOW' ? '#f0a500' : 'var(--accent)'

  return (
    <div className="context-banner">
      {recovery && (
        <div className="context-row">
          <span className="context-dot" style={{ background: zoneColor }} />
          <span className="context-text">{recovery.zone} {recovery.score}% Recovery</span>
        </div>
      )}
      {workoutType && <span className="context-workout">{workoutType}</span>}
      {nutrition && nutrition.current > 0 && (
        <span className="context-nutrition">
          {nutrition.current}{nutrition.target ? ` / ${nutrition.target}` : ''} cal
        </span>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add CSS for context banner**

Append to `frontend/src/index.css`:

```css
/* context banner */
.context-banner {
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.context-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.context-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.context-text {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.context-workout {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.context-nutrition {
  font-size: 0.8rem;
  color: var(--text-secondary);
}
```

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TS errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/context-banner.tsx frontend/src/index.css
git commit -m "feat: add context banner component for daily chat header"
```

---

## Task 6: Frontend — Day Card Component

**Files:**
- Create: `frontend/src/components/day-card.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create day-card.tsx**

```typescript
// frontend/src/components/day-card.tsx
interface DayCardProps {
  date: string
  workoutType: string | null
  recoveryZone: string | null
  caloriesTotal: number
  isToday: boolean
  onClick: () => void
}

export function DayCard({ date, workoutType, recoveryZone, caloriesTotal, isToday, onClick }: DayCardProps) {
  const zoneColor = recoveryZone === 'GREEN' ? 'var(--success)' : recoveryZone === 'YELLOW' ? '#f0a500' : recoveryZone === 'RED' ? 'var(--accent)' : 'var(--text-disabled)'
  const displayDate = isToday ? 'Today' : formatDate(date)
  const headline = workoutType || 'Rest Day'
  const stats = caloriesTotal > 0 ? `${caloriesTotal} cal` : ''

  return (
    <button className={`day-card${isToday ? ' today' : ''}`} onClick={onClick}>
      <div className="day-card-left">
        <span className="day-card-headline">{headline}</span>
        <span className="day-card-stats">{stats}</span>
      </div>
      <div className="day-card-right">
        {recoveryZone && <span className="day-card-dot" style={{ background: zoneColor }} />}
        <span className="day-card-date">{displayDate}</span>
      </div>
    </button>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}
```

- [ ] **Step 2: Add CSS for day cards**

Append to `frontend/src/index.css`:

```css
/* day cards */
.day-card {
  display: flex !important;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: var(--surface-1) !important;
  border: none;
  border-left: 3px solid var(--text-disabled);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  margin-bottom: 8px;
  text-align: left;
  transition: background var(--transition);
}

.day-card.today { border-left-color: var(--accent); }
.day-card:active { background: var(--surface-2) !important; }

.day-card-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.day-card-headline {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.day-card-stats {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.day-card-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.day-card-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.day-card-date {
  font-size: 0.75rem;
  color: var(--text-secondary);
}
```

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/day-card.tsx frontend/src/index.css
git commit -m "feat: add day history card component"
```

---

## Task 7: Frontend — API Methods for Chat Days

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add getChatDays and getChatDay to api.ts**

Add after the existing `getChatHistory` method:

```typescript
getChatDays: () => request<{ days: Array<{ date: string; message_count: number; workout_type: string | null; recovery_score: number | null; recovery_zone: string | null; calories_total: number }> }>('/chat/days'),
getChatDay: (date: string) => request<{ messages: Array<{ role: string; content: string; created_at: string }> }>(`/chat/day/${date}`),
```

Also update the `chat` method to accept an optional `date` parameter:

```typescript
chat: (message: string, workoutId?: number, date?: string) => request<import('./types').ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message, workout_id: workoutId ?? null, date: date ?? null }) }),
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add chat day API methods"
```

---

## Task 8: Frontend — Restructure Workout Tab for Daily Chat

**Files:**
- Modify: `frontend/src/screens/workout.tsx`
- Modify: `frontend/src/screens/workout-home.tsx`

This is the biggest frontend task. The Workout tab currently shows `WorkoutHome` when `activeWorkoutId` is null, and the chat interface when a workout/chat is active.

**State machine for the Workout tab:**

```
State A: DAILY_CHAT (default on mount)
  - Shows: header with "← Days" + date, ContextBanner, chat messages, input bar
  - chatDate = todayEastern()
  - "← Days" button → State B
  - "Start Workout" button (future Plan 2) → remains in State A but activates workout mode

State B: DAY_LIST
  - Shows: "Chats" title, list of DayCard components
  - Tap today's card → State A with chatDate = today
  - Tap a previous day → State A with chatDate = that day

State C: ACTIVE_WORKOUT (preserved from current code, Plan 2 will enhance)
  - activeWorkoutId > 0
  - Shows: workout chat header, messages, input bar
  - "End" button → State A
```

The existing `activeWorkoutId` state is preserved for workout-scoped chats. The new `chatDate` + `showDayList` states handle the daily chat flow. The `WorkoutHome` dashboard content (recovery banner, nutrition, plan preview) is replaced by the `ContextBanner` in State A and the "Start Workout" / "Chat with Claude" buttons become the default chat empty state message.

- [ ] **Step 1: Update workout.tsx to default to today's chat**

Rewrite `workout.tsx` to:
- Default state: `chatDate` set to today, chat view active
- `showDayList` state to toggle between chat and day list
- Load today's messages on mount via `api.getChatDay(today)`
- "← Days" header button sets `showDayList: true`
- Day list shows `DayCard` components from `api.getChatDays()`
- Tapping a day card sets `chatDate` to that day and shows chat

The existing workout mode (activeWorkoutId > 0) continues to work — it's a specific workout chat. General daily chat uses date-scoping.

```typescript
// key state changes in workout.tsx
const [chatDate, setChatDate] = useState<string>(todayEastern())
const [showDayList, setShowDayList] = useState(false)
const [messages, setMessages] = useState<Message[]>([])
const [activeWorkoutId, setActiveWorkoutId] = useState<number | null>(null)

// todayEastern helper for frontend
// 'en-CA' locale gives YYYY-MM-DD format, timeZone converts to Eastern
function todayEastern(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}
```

On mount, load today's chat messages:
```typescript
useEffect(() => {
  api.getChatDay(chatDate).then(r => {
    setMessages(r.messages.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })))
  }).catch(() => {})
}, [chatDate])
```

When sending messages, pass `date` parameter:
```typescript
const result = await api.chat(text, wid, chatDate)
```

- [ ] **Step 2: Update workout-home.tsx to be the day list view**

Rename `WorkoutHome` to serve as the day-list view. It shows:
- "Chats" header
- List of `DayCard` components from `getChatDays()`
- Today's card is prominent at top

```typescript
interface DayListProps {
  onSelectDay: (date: string) => void
}

export function DayList({ onSelectDay }: DayListProps) {
  const [days, setDays] = useState<Array<any>>([])
  useEffect(() => {
    api.getChatDays().then(r => setDays(r.days)).catch(() => {})
  }, [])

  const today = todayEastern()

  return (
    <div className="day-list-screen">
      <h2 className="day-list-title">Chats</h2>
      {days.map(d => (
        <DayCard
          key={d.date}
          date={d.date}
          workoutType={d.workout_type}
          recoveryZone={d.recovery_zone}
          caloriesTotal={d.calories_total}
          isToday={d.date === today}
          onClick={() => onSelectDay(d.date)}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Add CSS for day list screen**

```css
.day-list-screen {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
}

.day-list-title {
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: 16px;
}
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TS errors

- [ ] **Step 5: Manual test**

Start dev server: `cd frontend && npm run dev`
- Verify: Workout tab opens directly to today's chat
- Verify: Context banner shows at top of chat
- Verify: "← Days" button shows day history list
- Verify: Tapping a day opens that day's chat
- Verify: Sending a message in chat works and persists

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/workout.tsx frontend/src/screens/workout-home.tsx frontend/src/index.css
git commit -m "feat: restructure workout tab for daily chat with day history"
```

---

## Task 9: Final Integration Test + Full Suite

- [ ] **Step 1: Run full backend test suite**

Run: `.venv/bin/python -m pytest -x --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Restart service and verify**

```bash
systemctl --user restart spotme
```

Open the PWA, verify:
- Chat tab opens to today's chat
- Previous days accessible via "← Days"
- Messages persist between sessions
- Context banner shows recovery/workout/nutrition data

- [ ] **Step 4: Commit any fixes and push**

```bash
git push origin feat/diet-tab
```

---

## Next Plans

After this plan is complete:
- **Plan 2:** Workout Mode — `server/services/workout_sequencer.py`, `POST /api/workout/complete-set`, `frontend/src/components/set-card.tsx`, Claude prompt updates
- **Plan 3:** Program Drill-Down + Diet Drill-Down + Whoop Auto-Sync (parallelizable)
