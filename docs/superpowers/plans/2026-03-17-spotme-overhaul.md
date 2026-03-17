# SpotMe UX + Coaching Overhaul

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken coaching context, add recovery-aware training, overhaul workout UX with pre/during/post states, build history+progress screens, add morning briefing cron.

**Architecture:** Three layers of fixes — (A) backend foundation (Claude context, Whoop data, coaching rules), (B) workout UX overhaul (recovery banner, structured set logging, rest timer), (C) data screens + morning cron (history detail, progress trends, PRs, daily briefing via systemd timer + ntfy push).

**Tech Stack:** Python/FastAPI, React/TypeScript, SQLite/SQLAlchemy, Claude CLI, systemd timers, ntfy.sh push notifications.

---

## File Map

### Backend — Modify

| File | Lines | Changes |
|------|-------|---------|
| `server/services/claude_service.py` | 154 | Fix context: today's Whoop, past sets, recovery zones, coaching rules |
| `server/routes/chat.py` | 150 | Fix stale Whoop query, increase history to 10, fix memory save |
| `server/routes/workout.py` | 125 | Fix /next (use Claude), add /detail/{id}, improve /today, add /recent with exercises |
| `server/routes/progress.py` | 17 | Rewrite: 1RM calc (Epley), volume trends, Whoop trends, PRs |

### Backend — Create

| File | Purpose |
|------|---------|
| `server/routes/morning.py` | `GET /api/morning` — daily briefing: recovery + today's plan + coaching note |
| `server/services/notification_service.py` | Send push via ntfy.sh webhook |
| `deploy/spotme-morning.service` | systemd oneshot: sync Whoop + call morning endpoint + push notification |
| `deploy/spotme-morning.timer` | systemd timer: fires at 07:00 daily |

### Frontend — Modify

| File | Lines | Changes |
|------|-------|---------|
| `frontend/src/screens/workout.tsx` | 200 | Recovery banner, plan preview, structured set cards (extract home to workout-home.tsx if >200 lines) |
| `frontend/src/screens/history.tsx` | 90 | Exercise detail per workout, Whoop recovery badge (PRs tab extracted to prs-tab.tsx) |
| `server/schemas.py` | — | Add `set_suggestion` field to ChatResponse, add new response schemas |
| `frontend/src/components/set-card.tsx` | 21 | Show previous weight/reps, adjust button |
| `frontend/src/components/rest-timer.tsx` | 53 | Pause/resume, variable duration |
| `frontend/src/components/bottom-nav.tsx` | 27 | Keep 3 tabs but swap History icon |
| `frontend/src/api.ts` | 38 | Add new endpoints |
| `frontend/src/types.ts` | 73 | Add new types |
| `frontend/src/index.css` | 1428 | New styles for recovery banner, progress charts, workout detail |

### Frontend — Create

| File | Purpose |
|------|---------|
| `frontend/src/screens/progress.tsx` | Rewrite: 1RM trend chart, volume chart, Whoop recovery/HRV/strain trends |
| `frontend/src/screens/workout-home.tsx` | Extracted home screen (recovery banner + plan + start button) to keep workout.tsx under 200 lines |
| `frontend/src/components/recovery-banner.tsx` | Green/yellow/red recovery zone card with stats |
| `frontend/src/components/workout-detail.tsx` | Expandable workout card with exercises and sets |
| `frontend/src/components/prs-tab.tsx` | PRs tab content extracted from history.tsx to keep under 200 lines |

### Tests — Modify/Create

| File | Purpose |
|------|---------|
| `tests/test_workout.py` | Add tests for /next, /detail, improved /today |
| `tests/test_chat.py` | Fix stale Whoop test, test increased history |
| `tests/test_progress.py` | New: 1RM calculation, volume trends, PRs |
| `tests/test_morning.py` | New: morning briefing endpoint |

---

## Group A: Backend Foundation

### Task 1: Fix stale Whoop data in chat context

The chat endpoint queries most-recent WhoopData instead of today's. Claude sees 3-day-old recovery.

**Files:**
- Modify: `server/routes/chat.py:33-35`
- Modify: `server/routes/workout.py:78-81`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Write failing test — chat uses today's Whoop data**

```python
# tests/test_chat.py — add new test
def test_chat_uses_today_whoop_data(test_app, engine):
    """chat context should use today's whoop data, not stale data"""
    from datetime import date
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    # add old whoop data
    session.add(WhoopData(date="2026-03-15", recovery_score=90.0, hrv=80.0, resting_hr=48))
    # add today's whoop data
    session.add(WhoopData(date=date.today().isoformat(), recovery_score=45.0, hrv=35.0, resting_hr=65))
    session.add(UserProfile(name="Test"))
    session.commit()
    session.close()
    # the chat endpoint assembles context with whoop data
    # we can't easily test the context string, but we can test the query
    from server.routes.chat import _get_today_whoop
    db = TestSession()
    whoop = _get_today_whoop(db)
    assert whoop is not None
    assert whoop["recovery_score"] == 45.0  # today's, not 90
    db.close()
```

- [ ] **Step 2: Run test, verify it fails** (function doesn't exist yet)

Run: `.venv/bin/python -m pytest tests/test_chat.py::test_chat_uses_today_whoop_data -x --tb=short`

- [ ] **Step 3: Extract Whoop query into helper, filter by today**

In `server/routes/chat.py`, replace the inline Whoop query (lines 33-35) with:

```python
def _get_today_whoop(db: Session) -> dict | None:
    from datetime import date
    row = db.query(WhoopData).filter_by(date=date.today().isoformat()).first()
    if not row:
        return None
    return {
        "recovery_score": row.recovery_score,
        "hrv": row.hrv,
        "resting_hr": row.resting_hr,
        "sleep_score": row.sleep_score,
        "sleep_duration": row.sleep_duration,
        "strain": row.strain,
    }
```

Use it in the chat endpoint: `whoop = _get_today_whoop(db)`

Apply same fix in `server/routes/workout.py:78-81` for `/workout/today`.

- [ ] **Step 4: Run test, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chat.py -x --tb=short`

- [ ] **Step 5: Commit**

```
feat: fix stale whoop data — use today's date, not most recent
```

---

### Task 2: Add past set history to Claude context

Claude can't say "you did 225x5 last session" because it never sees past sets.

**Files:**
- Modify: `server/services/claude_service.py:47-82` (assemble_context)
- Modify: `server/routes/chat.py` (pass set history to assemble_context)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Write failing test — context includes recent sets**

```python
def test_context_includes_recent_sets():
    from server.services.claude_service import assemble_context
    set_history = [
        {"date": "2026-03-15", "exercise": "Bench Press", "weight": 225, "reps": 5, "rpe": 7.5},
        {"date": "2026-03-15", "exercise": "Bench Press", "weight": 225, "reps": 5, "rpe": 8.0},
    ]
    ctx = assemble_context(None, None, None, [], set_history=set_history)
    assert "225" in ctx
    assert "Bench Press" in ctx
    assert "Recent sets" in ctx
```

- [ ] **Step 2: Run test, verify it fails**

- [ ] **Step 3: Add set_history parameter to assemble_context**

```python
def assemble_context(program, workout, whoop, history, profile=None, memory=None, active_workout=None, set_history=None):
    # ... existing code ...
    if set_history:
        parts.append("\nRecent sets (last 3 workouts):")
        for s in set_history[-15:]:  # cap at 15 sets
            parts.append(f"  {s['date']} {s['exercise']}: {s['weight']}lbs x {s['reps']} @ RPE {s.get('rpe', '?')}")
    # ... rest of function ...
```

In `server/routes/chat.py`, query recent sets and pass them:

```python
recent_sets = (
    db.query(Set.weight, Set.reps, Set.rpe, Exercise.name, Workout.date)
    .join(Exercise, Set.exercise_id == Exercise.id)
    .join(Workout, Exercise.workout_id == Workout.id)
    .filter(Set.completed == True)
    .order_by(Workout.date.desc(), Exercise.name)
    .limit(15)
    .all()
)
set_history = [
    {"date": r.date, "exercise": r.name, "weight": r.weight, "reps": r.reps, "rpe": r.rpe}
    for r in recent_sets
]
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```
feat: add recent set history to Claude coaching context
```

---

### Task 3: Recovery-aware coaching rules in system prompt

Claude sees Whoop numbers but has no guidance on how to use them.

**Files:**
- Modify: `server/services/claude_service.py:12-44` (SYSTEM_PROMPT)
- Modify: `server/services/claude_service.py:73-75` (whoop context line)
- Test: `tests/test_chat.py`

- [ ] **Step 1: Write test — context includes recovery zone**

```python
def test_context_shows_recovery_zone():
    from server.services.claude_service import assemble_context
    whoop = {"recovery_score": 35.0, "hrv": 30.0, "sleep_score": 50.0, "strain": 15.0, "resting_hr": 70}
    ctx = assemble_context(None, None, whoop, [])
    assert "RED" in ctx or "red" in ctx.lower()
    assert "RPE" in ctx or "rpe" in ctx.lower()
```

- [ ] **Step 2: Run test, verify it fails**

- [ ] **Step 3: Add recovery zones to context + coaching rules to system prompt**

Add to SYSTEM_PROMPT:

```
## Recovery-Based Coaching

When Whoop data is available, adjust your coaching:
- GREEN (67-100% recovery): train as programmed, push intensity
- YELLOW (34-66% recovery): reduce RPE by 1, keep volume, monitor fatigue
- RED (0-33% recovery): suggest deload — reduce weight 10-15%, cut volume 30%, or swap to mobility/recovery work

Always mention the recovery zone when starting a workout. Factor sleep score into recommendations — below 60% sleep suggests shorter session.
```

Update the whoop context line in assemble_context:

```python
RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34

if whoop:
    recovery = whoop.get('recovery_score')
    zone = "GREEN" if recovery and recovery >= RECOVERY_GREEN else "YELLOW" if recovery and recovery >= RECOVERY_YELLOW else "RED"
    strain_str = f" | Strain {whoop['strain']}" if whoop.get('strain') else ""
    sleep_dur = whoop.get('sleep_duration')
    sleep_hrs = f" ({sleep_dur:.1f}h)" if isinstance(sleep_dur, (int, float)) else ""
    sleep_str = f" | Sleep {whoop.get('sleep_score', 'N/A')}%{sleep_hrs}" if whoop.get('sleep_score') else ""
    parts.append(f"Whoop [{zone}]: Recovery {recovery or 'N/A'}% | HRV {whoop.get('hrv', 'N/A')}{sleep_str}{strain_str} | RHR {whoop.get('resting_hr', 'N/A')}")
```

Note: `RECOVERY_GREEN` and `RECOVERY_YELLOW` constants are defined at module level and reused in the RecoveryBanner component (Task 5) and morning briefing (Task 13) to avoid DRY violations.

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```
feat: add recovery zones + coaching rules to Claude system prompt
```

---

### Task 4: Fix /workout/next — handle abbreviations and common plan formats

Current implementation does brittle line matching with hardcoded exercise keywords. Replace with smarter parsing that handles abbreviations (Mon/Tue), Day N patterns, and varied formats.

**Files:**
- Modify: `server/routes/workout.py:37-59`
- Test: `tests/test_workout.py`

- [ ] **Step 1: Write failing test**

```python
def test_next_workout_handles_structured_plan(test_app, engine):
    from datetime import date
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    session.add(SystemMemory(key="training_plan", content="""
Week 1-2: Upper Body Focus
- Mon/Thu: Bench 5x5, Incline DB 4x8, Tricep pushdowns 3x12
- Tue/Fri: Squat 5x5, RDL 3x8, Leg press 3x10
- Wed: Rest
"""))
    session.commit()
    session.close()
    resp = test_app.get("/api/workout/next")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] != "Check your program in Chat with Claude."
    assert len(data["summary"]) > 10
```

- [ ] **Step 2: Run test, verify it fails** (current regex matching won't parse "Mon/Thu" format)

- [ ] **Step 3: Rewrite /workout/next**

Replace the regex approach with a smarter parser that handles common formats:

```python
@router.get("/workout/next")
async def get_next_workout(db: Session = Depends(get_db)):
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"summary": "No program loaded. Tell Claude about your training plan in Chat."}

    today = date.today()
    day_name = today.strftime("%A")  # "Monday"
    day_abbrev = today.strftime("%a")  # "Mon"

    lines = memory.content.split("\n")
    # match lines containing today's day name or abbreviation
    for line in lines:
        lower = line.lower().strip()
        if not lower or lower.startswith("#"):
            continue
        if day_name.lower() in lower or day_abbrev.lower() in lower:
            clean = line.strip().strip("-*|").strip()
            if len(clean) > 10:
                return {"summary": clean}

    # fallback: look for day-of-week patterns like "Day 1" based on weekday number
    weekday_num = today.weekday()  # 0=Mon
    for line in lines:
        lower = line.lower().strip()
        if f"day {weekday_num + 1}" in lower and len(line.strip()) > 10:
            return {"summary": line.strip().strip("-*|").strip()}

    return {"summary": f"No {day_name} workout found in plan. Chat with Claude to update your program."}
```

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```
fix: /workout/next handles abbreviations and common plan formats
```

---

## Group B: Workout UX Overhaul

### Task 5: Recovery banner component

Show green/yellow/red recovery zone at the top of the workout screen before starting.

**Files:**
- Create: `frontend/src/components/recovery-banner.tsx`
- Modify: `frontend/src/screens/workout.tsx`
- Modify: `frontend/src/api.ts` (already has whoopLatest)
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create RecoveryBanner component**

```tsx
// frontend/src/components/recovery-banner.tsx
interface RecoveryBannerProps {
  recovery: number | null
  hrv: number | null
  sleep: number | null
  strain: number | null
}

function getZone(score: number | null): { label: string; color: string } {
  if (score == null) return { label: 'No data', color: 'var(--text-disabled)' }
  if (score >= 67) return { label: 'Green', color: 'var(--success)' }
  if (score >= 34) return { label: 'Yellow', color: '#f5a623' }
  return { label: 'Red', color: '#e57373' }
}

export function RecoveryBanner({ recovery, hrv, sleep, strain }: RecoveryBannerProps) {
  const zone = getZone(recovery)
  return (
    <div className="recovery-banner" style={{ borderLeftColor: zone.color }}>
      <div className="recovery-zone">
        <span className="recovery-zone-dot" style={{ background: zone.color }} />
        <span className="recovery-zone-label">{zone.label}</span>
        <span className="recovery-zone-score">{recovery != null ? `${Math.round(recovery)}%` : '—'}</span>
      </div>
      <div className="recovery-stats">
        <span>HRV {hrv != null ? Math.round(hrv) : '—'}</span>
        <span>Sleep {sleep != null ? `${Math.round(sleep)}%` : '—'}</span>
        <span>Strain {strain != null ? strain.toFixed(1) : '—'}</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add CSS for recovery banner**

```css
.recovery-banner {
  background: var(--surface-1);
  border-left: 4px solid var(--success);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 12px;
}
.recovery-zone {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.recovery-zone-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.recovery-zone-label {
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.recovery-zone-score {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-left: auto;
}
.recovery-stats {
  display: flex;
  gap: 16px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}
```

- [ ] **Step 3: Move WhoopStats type to types.ts**

Move the `WhoopStats` interface from `profile.tsx` to `frontend/src/types.ts` and import it in both `profile.tsx` and `workout.tsx`.

- [ ] **Step 4: Add recovery banner to workout home screen**

In `workout.tsx`, fetch Whoop latest on mount and show banner above "Start Workout":

```tsx
const [whoop, setWhoop] = useState<WhoopStats | null>(null)

useEffect(() => {
  api.whoopLatest().then(r => setWhoop(r.data)).catch(() => {})
}, [])

// in the home screen JSX, above the Start Workout button:
{whoop && <RecoveryBanner recovery={whoop.recovery_score} hrv={whoop.hrv} sleep={whoop.sleep_score} strain={whoop.strain} />}
```

- [ ] **Step 4: Build frontend, test visually**

Run: `cd frontend && npm run build`

- [ ] **Step 5: Commit**

```
feat: recovery banner with green/yellow/red zones on workout home
```

---

### Task 6: Pre-workout plan preview

Show today's planned workout before starting.

**Files:**
- Modify: `frontend/src/screens/workout.tsx`

- [ ] **Step 1: Show next workout preview on home screen**

The home screen already calls `getNextWorkout()` and shows it as "UP NEXT". Improve the display to be more prominent and actionable:

```tsx
// Replace the existing UP NEXT section with:
{nextSummary && nextSummary !== 'No program loaded.' && (
  <div className="workout-plan-preview">
    <span className="workout-plan-label">TODAY'S PLAN</span>
    <p className="workout-plan-text">{nextSummary}</p>
  </div>
)}
```

Add CSS:

```css
.workout-plan-preview {
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  margin-bottom: 12px;
}
.workout-plan-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent);
}
.workout-plan-text {
  font-size: 0.85rem;
  color: var(--text-primary);
  margin-top: 4px;
  line-height: 1.4;
}
```

- [ ] **Step 2: Build and test**

- [ ] **Step 3: Commit**

```
feat: today's plan preview on workout home screen
```

---

### Task 7: Structured set suggestions (replace regex)

Replace brittle regex parsing with Claude returning structured JSON set suggestions.

**Files:**
- Modify: `server/services/claude_service.py:12-44` (system prompt)
- Modify: `frontend/src/screens/workout.tsx:107-117` (set extraction)
- Modify: `server/routes/chat.py` (pass through set_suggestions from Claude response)

- [ ] **Step 1: Update system prompt to return structured set suggestions**

Add to the JSON response format in SYSTEM_PROMPT:

```
- "set_suggestion" is optional — when recommending a specific set, include:
  {"exercise": "Bench Press", "weight": 225, "reps": 5, "basis": "based on last session + green recovery"}
```

- [ ] **Step 2: Add set_suggestion to ChatResponse schema**

In `server/schemas.py`, add the field to `ChatResponse`:
```python
class ChatResponse(BaseModel):
    response: str
    layout: dict | None = None
    set_suggestion: dict | None = None
```

- [ ] **Step 3: Update Claude response parsing in ClaudeService.chat()**

```python
return {
    "response": parsed.get("response", raw_text),
    "layout": layout,
    "profile": parsed.get("profile"),
    "memory_update": parsed.get("memory_update"),
    "set_suggestion": parsed.get("set_suggestion"),
}
```

- [ ] **Step 4: Update chat route to pass through set_suggestion**

- [ ] **Step 4: Update frontend to prefer structured suggestions, fallback to regex**

```tsx
// in workout.tsx send():
const suggestion = data.set_suggestion || extractSetFromText(data.response)
const assistantMsg: Message = {
  role: 'assistant',
  content: data.response,
  setCard: suggestion ? { exercise: suggestion.exercise, weight: suggestion.weight, reps: suggestion.reps, basis: suggestion.basis } : undefined,
}
```

Keep the regex as a fallback but prefer structured data.

- [ ] **Step 5: Run tests, commit**

```
feat: structured set suggestions from Claude, regex as fallback
```

---

### Task 8: Rest timer improvements

Add pause/resume and variable duration.

**Files:**
- Modify: `frontend/src/components/rest-timer.tsx`
- Modify: `frontend/src/screens/workout.tsx` (use the component properly)

- [ ] **Step 1: Rewrite RestTimer with pause/resume**

```tsx
export function RestTimer({ seconds, compact, onComplete }: RestTimerProps) {
  const [remaining, setRemaining] = useState(seconds)
  const [active, setActive] = useState(false)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    if (!active || remaining <= 0) return
    const id = setInterval(() => {
      setRemaining(prev => {
        if (prev <= 1) {
          setActive(false)
          onCompleteRef.current?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [active])

  const toggle = () => setActive(!active)
  const reset = () => { setActive(false); setRemaining(seconds) }
  const addTime = (s: number) => setRemaining(prev => prev + s)

  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60
  const display = `${mins}:${secs.toString().padStart(2, '0')}`

  if (compact) return <span className="rest-timer-compact">{display}</span>

  return (
    <div className="rest-timer">
      <span className="rest-timer-display">{display}</span>
      <div className="rest-timer-controls">
        <button className="rest-btn" onClick={toggle}>{active ? 'Pause' : remaining < seconds ? 'Resume' : 'Start'}</button>
        <button className="rest-btn rest-btn-add" onClick={() => addTime(30)}>+30s</button>
        <button className="rest-btn rest-btn-reset" onClick={reset}>Reset</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add CSS for rest timer buttons**

- [ ] **Step 3: Wire into workout.tsx — use RestTimer component instead of inline countdown**

- [ ] **Step 4: Build and test**

- [ ] **Step 5: Commit**

```
feat: rest timer with pause/resume and +30s button
```

---

### Task 9: Auto-fill previous weights on set card

**Files:**
- Modify: `frontend/src/components/set-card.tsx`
- Modify: `server/routes/workout.py` (add /exercise/last endpoint)
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add /exercise/last endpoint**

```python
@router.get("/exercise/last/{name}")
async def get_last_exercise(name: str, db: Session = Depends(get_db)):
    """get the most recent completed sets for an exercise"""
    sets = (
        db.query(Set.weight, Set.reps, Set.rpe, Workout.date)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .join(Workout, Exercise.workout_id == Workout.id)
        .filter(Exercise.name.ilike(f"%{name}%"), Set.completed == True)
        .order_by(Workout.date.desc())
        .limit(5)
        .all()
    )
    return {"sets": [{"weight": s.weight, "reps": s.reps, "rpe": s.rpe, "date": s.date} for s in sets]}
```

- [ ] **Step 2: Update SetCard to show "Last time" info**

```tsx
export function SetCard({ exercise, weight, reps, basis, lastSet, onStart }: SetCardProps) {
  return (
    <div className="set-card">
      <span className="set-card-label">SUGGESTED SET</span>
      <span className="set-card-exercise">{exercise}</span>
      <span className="set-card-prescription">{weight} lbs x {reps}</span>
      {lastSet && <span className="set-card-last">Last: {lastSet.weight}x{lastSet.reps} @ RPE {lastSet.rpe || '?'}</span>}
      {basis && <span className="set-card-basis">{basis}</span>}
      <button className="set-card-start" onClick={onStart}>Start Set</button>
    </div>
  )
}
```

- [ ] **Step 3: Fetch last set data when Claude suggests an exercise**

- [ ] **Step 4: Test and commit**

```
feat: show previous weight/reps on set suggestion cards
```

---

## Group C: History + Progress

### Task 10: History with exercise detail + Whoop recovery

**Files:**
- Modify: `server/routes/workout.py` (update /recent to include exercises + whoop)
- Modify: `frontend/src/screens/history.tsx`
- Create: `frontend/src/components/workout-detail.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Update /recent to return exercises and Whoop data**

```python
@router.get("/workout/recent")
async def get_recent_workouts(db: Session = Depends(get_db)):
    workouts = db.query(Workout).order_by(Workout.date.desc()).limit(20).all()
    result = []
    for w in workouts:
        exercises = db.query(Exercise).filter_by(workout_id=w.id).order_by(Exercise.order).all()
        whoop = db.query(WhoopData).filter_by(date=w.date).first()
        exercise_list = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            exercise_list.append({
                "name": ex.name,
                "sets": [{"weight": s.weight, "reps": s.reps, "rpe": s.rpe} for s in sets],
            })
        result.append({
            "id": w.id, "date": w.date, "type": w.type,
            "status": w.status, "duration": w.duration,
            "exercises": exercise_list,
            "recovery": whoop.recovery_score if whoop else None,
        })
    return result
```

- [ ] **Step 2: Create WorkoutDetail component**

Expandable card showing exercises and sets for a past workout.

- [ ] **Step 3: Update History screen**

Show recovery badge (colored dot), exercise summary on each card. Tap to expand and see full sets.

- [ ] **Step 4: Test, commit**

```
feat: history shows exercises, sets, and Whoop recovery per workout
```

---

### Task 11: PRs tracking and detection

**Files:**
- Modify: `server/routes/progress.py` (add PR calculation)
- Modify: `frontend/src/screens/history.tsx` (PRs tab)

- [ ] **Step 1: Add PR endpoint**

```python
@router.get("/progress/prs")
async def get_prs(db: Session = Depends(get_db)):
    """calculate estimated 1RM PRs per exercise using Epley formula"""
    exercises = db.query(Exercise.name).distinct().all()
    prs = []
    for (name,) in exercises:
        best = (
            db.query(Set.weight, Set.reps, Workout.date)
            .join(Exercise, Set.exercise_id == Exercise.id)
            .join(Workout, Exercise.workout_id == Workout.id)
            .filter(Exercise.name == name, Set.completed == True, Set.reps <= 10)
            .order_by((Set.weight * (1 + Set.reps / 30.0)).desc())  # Epley
            .first()
        )
        if best:
            e1rm = round(best.weight * (1 + best.reps / 30.0), 1)
            prs.append({"exercise": name, "weight": best.weight, "reps": best.reps, "e1rm": e1rm, "date": best.date})
    prs.sort(key=lambda x: x["e1rm"], reverse=True)
    return {"prs": prs}
```

- [ ] **Step 2: Build PRs tab in History screen**

List exercises with best estimated 1RM, date achieved, and the set that produced it.

- [ ] **Step 3: Test, commit**

```
feat: PR tracking with Epley 1RM estimates per exercise
```

---

### Task 12: Progress screen

**Files:**
- Rewrite: `frontend/src/screens/progress.tsx`
- Modify: `server/routes/progress.py` (expand endpoint)
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Expand /progress endpoint**

Return structured data:
```python
{
    "bench_trend": [{"date": "2026-03-15", "e1rm": 285.0, "best_set": "225x5"}],
    "volume_trend": [{"date": "2026-03-15", "total_lbs": 12500}],
    "whoop": {
        "recovery": [{"date": "2026-03-15", "value": 72.0}],
        "hrv": [{"date": "2026-03-15", "value": 65.0}],
        "strain": [{"date": "2026-03-15", "value": 12.5}],
    },
}
```

- [ ] **Step 2: Build Progress screen with simple trend displays**

Use CSS-only bar charts (no chart library needed). Show:
- Estimated 1RM trend (last 30 days)
- Total volume per workout
- Whoop recovery/HRV/strain trends

- [ ] **Step 3: Wire into App.tsx navigation**

Replace History tab with a segmented view: Workouts | Progress | PRs (all inside History screen).

- [ ] **Step 4: Test, commit**

```
feat: progress screen with 1RM trends, volume, and Whoop data
```

---

## Group D: Morning Briefing

### Task 13: Morning briefing API endpoint

**Files:**
- Create: `server/routes/morning.py`
- Create: `server/services/notification_service.py`
- Modify: `server/main.py` (register route)

- [ ] **Step 1: Create morning briefing endpoint**

```python
# server/routes/morning.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from server.database import get_db
from server.models import WhoopData, SystemMemory

router = APIRouter()

@router.get("/morning")
async def morning_briefing(db: Session = Depends(get_db)):
    today = date.today()
    day_name = today.strftime("%A")

    # get today's whoop data
    whoop = db.query(WhoopData).filter_by(date=today.isoformat()).first()
    recovery = whoop.recovery_score if whoop else None
    zone = "GREEN" if recovery and recovery >= 67 else "YELLOW" if recovery and recovery >= 34 else "RED" if recovery else "UNKNOWN"

    # get today's planned workout
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    plan = "Rest day"
    if memory:
        for line in memory.content.split("\n"):
            lower = line.lower().strip()
            if day_name.lower() in lower or today.strftime("%a").lower() in lower:
                clean = line.strip().strip("-*|").strip()
                if len(clean) > 10:
                    plan = clean
                    break

    # build coaching note
    if zone == "RED":
        coaching = "Recovery is low. Consider a deload or mobility session."
    elif zone == "YELLOW":
        coaching = "Moderate recovery. Train but dial back intensity by 1 RPE."
    elif zone == "GREEN":
        coaching = "Well recovered. Push it today."
    else:
        coaching = "No Whoop data. Sync your Whoop to get recovery-based coaching."

    return {
        "date": today.isoformat(),
        "day": day_name,
        "zone": zone,
        "recovery": recovery,
        "hrv": whoop.hrv if whoop else None,
        "sleep_score": whoop.sleep_score if whoop else None,
        "plan": plan,
        "coaching": coaching,
    }
```

- [ ] **Step 2: Create notification service**

```python
# server/services/notification_service.py
import httpx
import logging

logger = logging.getLogger(__name__)

from server.config import settings

# add to Settings in config.py: ntfy_topic: str = ""
# loaded from NTFY_TOPIC env var in .env

async def send_morning_notification(briefing: dict):
    if not settings.ntfy_topic:
        logger.info("ntfy_topic not configured, skipping notification")
        return

    ntfy_url = f"https://ntfy.sh/{settings.ntfy_topic}"
    zone = briefing["zone"]
    recovery = briefing.get("recovery")
    plan = briefing["plan"]
    coaching = briefing["coaching"]

    title = f"SpotMe — {briefing['day']} [{zone}]"
    recovery_str = f"Recovery {round(recovery)}%" if recovery else "No Whoop data"
    body = f"{recovery_str}\n{plan}\n{coaching}"

    try:
        async with httpx.AsyncClient() as client:
            await client.post(ntfy_url, content=body.encode(), headers={
                "Title": title,
                "Priority": "3" if zone == "RED" else "default",
                "Tags": "muscle" if zone == "GREEN" else "warning" if zone == "YELLOW" else "sleeping",
            })
        logger.info("morning notification sent")
    except Exception as e:
        logger.warning("morning notification failed: %s", e)
```

- [ ] **Step 3: Register route in main.py**

- [ ] **Step 4: Write test, commit**

```
feat: morning briefing endpoint with recovery zone + planned workout
```

---

### Task 14: systemd timer for morning briefing

**Files:**
- Create: `deploy/spotme-morning.service`
- Create: `deploy/spotme-morning.timer`

- [ ] **Step 1: Create morning service**

```ini
# deploy/spotme-morning.service
[Unit]
Description=SpotMe morning briefing
After=network.target

[Service]
Type=oneshot
WorkingDirectory=%h/spotme
ExecStart=/bin/bash -c '%h/spotme/.venv/bin/python -c "import asyncio, httpx; asyncio.run(httpx.AsyncClient().get(\"http://127.0.0.1:8000/api/whoop/sync\"))" && %h/spotme/.venv/bin/python -c "import asyncio, httpx; r = asyncio.run(httpx.AsyncClient().get(\"http://127.0.0.1:8000/api/morning\")); import json; briefing = r.json(); from server.services.notification_service import send_morning_notification; asyncio.run(send_morning_notification(briefing))"'
```

Actually, create a simple Python script instead:

- [ ] **Step 1b: Create morning script**

```python
# server/scripts/morning_briefing.py
"""run by systemd timer at 07:00 — syncs whoop then sends morning push"""
import asyncio
import httpx

BASE = "http://127.0.0.1:8000/api"

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        await client.get(f"{BASE}/whoop/sync")
        # notify=true triggers push notification server-side
        await client.get(f"{BASE}/morning?notify=true")

if __name__ == "__main__":
    asyncio.run(main())
```

The `/api/morning` endpoint accepts `?notify=true` query param to trigger the push notification itself, keeping the script as pure HTTP calls.

- [ ] **Step 2: Create systemd timer**

```ini
# deploy/spotme-morning.service
[Unit]
Description=SpotMe morning briefing
After=network.target

[Service]
Type=oneshot
WorkingDirectory=%h/spotme
ExecStart=%h/spotme/.venv/bin/python -m server.scripts.morning_briefing
Environment=PATH=%h/.local/bin:/usr/bin

# deploy/spotme-morning.timer
[Unit]
Description=SpotMe morning briefing timer

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Install and enable timer**

```bash
cp deploy/spotme-morning.service deploy/spotme-morning.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now spotme-morning.timer
```

- [ ] **Step 4: Test manually**

```bash
systemctl --user start spotme-morning.service
journalctl --user -u spotme-morning -n 20
```

- [ ] **Step 5: Commit**

```
feat: morning briefing cron — syncs Whoop at 7am, pushes recovery + plan via ntfy
```

---

## Execution Order

Tasks can be parallelized where noted:

```
Phase 1 (Foundation) — sequential:
  Task 1: Fix stale Whoop data
  Task 2: Add set history to context
  Task 3: Recovery zones + coaching rules
  Task 4: Fix /workout/next

Phase 2 (Workout UX) — after Phase 1:
  Task 5+6: Recovery banner + Plan preview (sequential — both touch workout.tsx)
  Task 7: Structured set suggestions
  Task 8: Rest timer improvements  } parallel with Task 7
  Task 9: Auto-fill previous weights (after Task 7)

Phase 3 (Data screens) — can parallel after Phase 2:
  Task 10: History detail          }
  Task 11: PRs tracking            } parallel
  Task 12: Progress screen         }

Phase 4 (Morning cron) — independent:
  Task 13: Morning briefing API    }
  Task 14: systemd timer           } sequential
```

Total: 14 tasks, estimated 4 parallel work streams.
