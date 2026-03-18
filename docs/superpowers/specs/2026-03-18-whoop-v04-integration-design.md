# Whoop v0.4 Integration Design

Full integration of whoop-write-api v0.4 into SpotMe. Replaces dual-token auth with unified Cognito, adds automatic workout/journal syncing, Claude tool-use for ad-hoc writes, and active biometric coaching.

Supersedes GitHub issue #4 and prior issues #1, #3.

---

## Design Decisions

- **Approach:** Hybrid (C) — deterministic auto-sync in the service layer for predictable writes (workouts, journal), Claude tools for ad-hoc writes (sauna, weight, alarm). Chosen over pure service-layer (inflexible) and pure Claude-orchestrator (adds latency to critical paths).
- **Read strategy:** Cache-first with smart sync triggers. WhoopData table is the single read source. Live API calls only on sync triggers, never on read.
- **Write philosophy:** If it enters SpotMe, it flows to Whoop automatically. Ad-hoc Whoop-only writes confirmed in chat.
- **Coaching model:** Active — Claude adjusts intensity, volume, and rest based on biometrics. Personalized thresholds, not generic.
- **Auth:** Single Cognito login, auto-refresh, never expires unless revoked. Old OAuth kept as disabled fallback.

---

## Section 1: Auth & Client Factory

### Cognito Auth (replaces dual-token system)

User enters Whoop email/password one time on the Profile screen. `CognitoAuth().login()` exchanges credentials for a `TokenSet` stored in the `WhoopToken` table. Password is never stored.

```
POST /api/whoop/login
  -> CognitoAuth().login(email, password)
  -> TokenSet {access_token, refresh_token, expires_at}
  -> Upsert into WhoopToken table (single row)
```

### Client Factory: `get_whoop_client(db)`

Every Whoop operation uses this factory. It loads tokens from DB, creates a client with an `on_token_refresh` callback that auto-persists refreshed tokens to SQLite.

**Note:** SpotMe uses sync SQLAlchemy sessions. The `on_token_refresh` callback signature (sync vs async) must match what `WhoopClient` expects — verify against the v0.4 library. The `expires_at` field on `TokenSet` is a unix float; convert to/from the DB's DateTime column at the boundary.

```python
def get_whoop_client(db: Session) -> WhoopClient:
    stored = db.query(WhoopToken).first()
    if not stored:
        raise HTTPException(400, "whoop not connected")

    token_set = TokenSet(
        access_token=stored.access_token,
        refresh_token=stored.refresh_token,
        expires_at=stored.expires_at.timestamp(),  # DateTime -> unix float
    )

    def persist_refreshed_tokens(new_tokens: TokenSet):
        stored.access_token = new_tokens.access_token
        stored.refresh_token = new_tokens.refresh_token
        stored.expires_at = datetime.fromtimestamp(new_tokens.expires_at)
        db.commit()

    return WhoopClient(
        token_set=token_set,
        on_token_refresh=persist_refreshed_tokens,
    )
```

Usage: `async with get_whoop_client(db) as client:` — reuses HTTP connection, auto-refreshes tokens. If the library's callback contract is async, wrap with `asyncio.to_thread` or make the factory async accordingly.

### Error Handling Wrapper

Extract a reusable pattern so call sites only handle the happy path:

```python
from whoop import WhoopAuthExpiredError, WhoopAPIError, WhoopRateLimitError

# every call site follows this hierarchy:
# WhoopAuthExpiredError -> terminal, user must re-login
# WhoopRateLimitError   -> retry after e.retry_after seconds
# WhoopAPIError         -> log and degrade gracefully
```

Pseudocode for the wrapper (returns client or None on error):

```python
async def whoop_operation(db: Session) -> WhoopClient | None:
    try:
        return get_whoop_client(db)
    except WhoopAuthExpiredError:
        mark_whoop_disconnected(db)
        return None
    except Exception:
        return None

# usage pattern:
client = await whoop_operation(db)
if client is None:
    return graceful_fallback()
async with client:
    result = await client.get_recovery()
```

For write operations that need error-specific handling:

```python
async def whoop_write(db, coro_fn):
    client = await whoop_operation(db)
    if client is None:
        return {"synced": False, "error": "whoop not available"}
    try:
        async with client:
            return await coro_fn(client)
    except WhoopRateLimitError as e:
        logger.warning(f"whoop rate limited, retry after {e.retry_after}s")
        return {"synced": False, "error": "rate limited", "retry_after": e.retry_after}
    except WhoopAPIError as e:
        logger.warning(f"whoop API error {e.status_code}: {e}")
        return {"synced": False, "error": str(e)}
```

### Removed

- OAuth authorize/callback routes (Developer API)
- SystemMemory `whoop_write_token` storage
- Separate read vs write token paths
- `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET` env vars
- No new env vars needed (Cognito uses Whoop's built-in client ID)

### Old OAuth Fallback

Keep old OAuth code as disabled fallback for 1-2 months. Comment out routes but don't delete. Remove after Cognito auth is proven stable in production.

### Graceful Degradation (unchanged)

- App works 100% without Whoop connected
- All Whoop imports remain lazy (inside functions)
- All Whoop calls wrapped in try/except
- Failed writes queue to WhoopSyncQueue for retry

### Migration

**Prerequisite: Initialize Alembic.** No Alembic setup exists in the project. P0 step: `alembic init`, configure `env.py` for existing SQLite, create initial migration capturing current schema.

- WhoopToken: `expires_at` column already exists as `DateTime(nullable=True)`. Keep as DateTime — convert to/from unix float at the `TokenSet` boundary. No type migration needed.
- Wipe existing OAuth token rows (incompatible with Cognito)
- Remove SystemMemory `whoop_write_token` and `whoop_oauth_state` rows
- Profile screen shows one-time migration note: "Whoop auth has been upgraded. Please sign in again to reconnect." Track via SystemMemory `whoop_migration_shown` flag.
- All existing WhoopData history preserved

### Profile Screen Auth UX

- Value prop above login form: "Connect to sync workouts, track recovery, and get coaching adjusted to your body."
- Password reassurance below form: "Password is used once to authenticate, then discarded."
- On first connection success: foreground sync with brief loading state ("Syncing your Whoop data...") so user sees their data immediately — the payoff moment.

---

## Section 2: Hybrid Read & Sync Layer

### Principle

WhoopData table is the single read source for all consumers: ContextBanner, RecoveryBanner, Claude context, progress charts, active coaching. No consumer hits the Whoop API directly.

### Smart Sync Triggers

| Trigger | Behavior | Staleness check |
|---------|----------|-----------------|
| App opens | Background sync (silent, no spinner) | Skip if data < 2 hours old |
| Workout starts | Optimistic start with background refresh | Always sync, but don't block workout start |
| Manual sync button | Foreground sync on Profile | Always sync |
| Background timer | systemd, every 4 hours | Safety net, 2-hour dedup window |
| Claude needs context | Read from cache only | Never triggers sync |

### Optimistic Workout Start

Don't block workout start on sync. Start immediately with cached data. Background sync fires. If recovery data changes significantly after sync completes, Claude adjusts on the next message. Recovery doesn't change fast enough intra-day to justify a loading spinner.

### Sync Lock

Module-level `asyncio.Lock` prevents concurrent syncs within the FastAPI process (app-open + workout-start race condition). Second caller waits for first result. This only guards intra-process concurrency — for cross-process dedup (e.g., systemd timer running a separate CLI process), the 2-hour staleness check on `synced_at` in the database is the guard.

### Staleness Threshold: 2 Hours

Recovery data is a daily snapshot. 2-hour threshold halves unnecessary API calls vs 1-hour, kinder to rate limits on a reverse-engineered API.

### Stale Data Indicator

If WhoopData date doesn't match today, ContextBanner shows `GREEN 78% (yesterday)`. Claude's context also gets this flag: "Note: Whoop data is from yesterday, may not reflect current readiness."

### Consecutive Failure Tracking

Track consecutive sync failures. After 3 consecutive failures, set `whoop_needs_attention` flag. ContextBanner shows warning. Unify with existing CLI `whoop_status` tracking in SystemMemory.

### Sync Function (enhanced)

```python
async def sync_whoop_biometrics(db: Session, force: bool = False):
    if not force:
        latest = db.query(WhoopData).order_by(...).first()
        if latest and latest.synced_at > (now - 2hrs):
            return {"skipped": True, "reason": "fresh"}

    async with await get_whoop_client(db) as client:
        recovery = await client.get_recovery()
        sleep = await client.get_sleep()
        # strain from cycles (graceful if scope missing)

    # upsert into WhoopData by date
    return {"synced": True}
```

### WhoopData Table

No schema change needed. Existing fields: date, recovery_score, hrv, resting_hr, sleep_score, sleep_duration, strain, synced_at.

### Background Timer (simplified)

Existing systemd timer every 4 hours. CLI logic unchanged, just uses `get_whoop_client()` now. Dedup window: 2 hours.

---

## Section 3: Auto-Write Layer

### Principle

If it enters SpotMe, it flows to Whoop automatically. Two write paths split by predictability.

### Path 1: Workout Auto-Sync (deterministic, service layer)

**Trigger:** `POST /api/workout/complete` — after marking workout as completed.

**Exercise ID Mapping:**
- Claude maps exercises to Whoop catalog IDs during workout planning (not fuzzy match at sync time)
- Claude already knows exercise context (barbell vs dumbbell, flat vs incline) and picks from the 310-item catalog
- Resolved ID stored in `Exercise.whoop_exercise_id` for reuse
- Service layer passes through the cached mapping — no intelligence needed at sync time
- Unmapped exercises still sync, just without Whoop's exercise ID

**Exercise Catalog Lifecycle:**
1. On login success: fetch full catalog, cache in `ExerciseCatalog` table
2. Weekly refresh via background timer
3. `search_exercise_catalog` tool queries local cache, never Whoop API
4. If cache is empty (migration edge case), tool triggers a one-time fetch
5. Alembic migration needed for new table

**Payload:**
```python
for exercise in workout.exercises:
    DetailedExercise(
        exercise_id=exercise.whoop_exercise_id,
        name=exercise.name,
        sets=[
            ExerciseSet(reps=s.actual_reps, weight=s.actual_weight)
            for s in exercise.completed_sets
        ]
    )
```

For timed exercises (planks, holds): `ExerciseSet(time_seconds=60)`.

**Failure:** SyncQueue row (status=pending), retry on next app open, max 3 attempts.

**Transaction Boundaries:**
- SpotMe DB commit happens FIRST (mark workout completed)
- Then Whoop activity creation + exercise linking (one try/except block)
- Then journal sync (separate try/except block)
- Whoop failures never roll back local completion
- Each Whoop write is independent

**Sync Feedback:** Part of Claude's natural workout summary:
```
"Great session — 5 exercises, 22 sets.
 Bench topped out at 275x3 @RPE 8.
 Synced to Whoop."
```
Or: `"Whoop sync queued — will retry later."`

### Path 2: Meal -> Journal Auto-Sync (deterministic, service layer)

**Claude extracts journal signals during meal parsing** — no keyword regex needed. Claude already reads the meal description and now returns an additional `journal_signals` field:

```python
# Claude's meal parse response (enhanced)
{
    "calories": 550,
    "protein": 45,
    "journal_signals": {"caffeine": 1}
}
```

Claude handles edge cases naturally:
- "decaf latte" -> caffeine: 0
- "coffee with Mike" -> caffeine: 1
- "virgin mojito" -> alcohol: false
- "hard seltzer" -> alcohol: true

**No DailyJournal table.** Compute from Meal records on-the-fly:
```python
today_meals = db.query(Meal).filter(date=today).all()
caffeine = sum(m.journal_signals.get("caffeine", 0) for m in today_meals)
alcohol = any(m.journal_signals.get("alcohol", False) for m in today_meals)
late_meal = any(m.logged_at.hour >= 20 for m in today_meals)
protein = sum(m.protein or 0 for m in today_meals)
```

Add `journal_signals` JSON column to Meal model. At most 5-6 meals/day — trivial query. Single source of truth.

**Journal signals schema:**
- `caffeine` (int, default 0) — count of caffeinated drinks
- `alcohol` (bool, default false) — any alcoholic drink mentioned

Late meal detection: computed from `Meal.created_at` (serves as meal timestamp), not stored in `journal_signals`. Flag if `created_at.hour >= 20`.

Protein: computed from `Meal.protein` column (already exists), not stored in `journal_signals`.

**Sync:** On each meal log, compute accumulated journal state and sync full day to Whoop via `log_journal()`. Idempotent (overwrite). Last sync is always the complete picture.

**One-time education:** On first meal log after Whoop connection, Claude mentions it once:
```
"Logged: burger, fries, beer — 850 cal, 28g protein.
 Since you have Whoop connected, I'm also tracking
 caffeine and alcohol from your meals to your Whoop
 journal. I won't mention this again unless something
 looks off."
```

### Path 3: Claude Ad-Hoc Tools (conversational, Claude tool-use)

**Internal dispatch, not HTTP routes.** The frontend never calls these. They execute server-side during Claude's tool-use loop:

```python
# server/services/whoop_tools.py
TOOL_HANDLERS = {
    "create_whoop_activity": handle_create_activity,
    "update_whoop_weight": handle_update_weight,
    "set_whoop_alarm": handle_set_alarm,
    "delete_whoop_activity": handle_delete_activity,
    "search_exercise_catalog": handle_search_catalog,
}

async def execute_whoop_tool(name, params, db):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"unknown tool: {name}"}
    return await handler(params, db)
```

**Confirmation Pattern — risk-tiered:**

| Risk | Actions | Behavior |
|------|---------|----------|
| Low | Create activity, log journal | Execute, then announce: "Logged 20-min sauna to Whoop." |
| Medium | Update weight | Execute, then confirm value: "Updated Whoop weight to 255 lbs." |
| High | Delete activity, set alarm | Confirm BEFORE executing: "Delete the sauna from 6pm?" |

Claude announces what it did in chat (honors "confirm in chat" preference). User corrects if wrong, Claude fixes.

**Ambiguous intent guard:** Claude only triggers ad-hoc writes when intent is clear. If ambiguous ("I did yoga for an hour" in casual chat), Claude asks: "Want me to log the yoga session to Whoop?"

**Activity types:** sauna, ice_bath, meditation, yoga, stretching, running, cycling, hiking, swimming, walking.

**Exercise catalog search limit:** Return top 10 matches to keep Claude's context manageable on broad queries.

### Retry & Queue (unified)

WhoopSyncQueue handles ALL write failures: workout syncs, journal syncs, ad-hoc activity syncs. Retry trigger: app open (background). Max retries: 3. After 3 failures: surface on Profile screen.

**Schema changes needed:** Current `WhoopSyncQueue` has a `workout_id` FK and no fields for journal or ad-hoc payloads. Add:
- `sync_type` column (String: "workout", "journal", "activity")
- Make `workout_id` nullable (journal/activity syncs don't have one)
- `payload` JSON column already exists — use for all sync types

### Rate Limiting

Soft limit: 20 API calls per hour. In-memory counter with hourly reset (resets on server restart — acceptable for a soft limit). If exceeded: skip non-essential sync triggers, queue writes instead of sending immediately, log a warning. Essential reads (manual sync button) still fire. Defensive, not restrictive. Expected busy-day load: ~10-12 calls.

---

## Section 4: Claude Coaching & Context Assembly

### Principle

Claude is an active coach, not a data display. Whoop data informs every coaching decision. Personalized thresholds based on the user's patterns, not generic defaults.

### Enhanced Context Assembly

New additions to `assemble_context()`:

- Full Whoop snapshot: recovery_score, hrv, resting_hr, sleep_score, sleep_hours, strain
- HRV trend: 7-day average vs today (computed via `AVG()` over 7 WhoopData rows — trivially fast)
- Whoop tool availability flag
- Exercise catalog availability flag
- Stale data flag if WhoopData date != today

Total context: ~3850 tokens (within 4000 token budget).

### Tool-Use Loop (P0 Infrastructure)

SpotMe currently does simple text chat. **Critical prerequisite:** The existing `_call_claude()` implementation uses the `claude` CLI binary via `asyncio.create_subprocess_exec` in `--print` mode. The CLI does not support tool-use — it's text-in/text-out only. This must be replaced with direct `anthropic.AsyncAnthropic` SDK calls using the messages API, which supports `tool_use` content blocks and multi-turn tool loops. This is a significant refactor of `claude_service.py`.

New flow:

```
Frontend -> POST /api/chat -> server calls Claude SDK (messages API)
  -> Claude returns tool_use?
     yes: execute_whoop_tool() -> tool_result -> Claude SDK again
          (may loop, max 3 iterations, 30s timeout)
     no:  return text response
  -> Frontend gets final response
```

Key decisions:
- Max tool-use iterations: 3
- Full loop timeout: 30 seconds
- Tool + layout: tool executes first, layout returned with final response
- Tool results stored as assistant messages, not shown to user

**This is the single biggest infrastructure change and must be built first.**

### Tool Definitions

```json
[
  {
    "name": "create_whoop_activity",
    "description": "Log an activity to the user's Whoop",
    "params": {
      "activity_type": "sauna|ice_bath|meditation|yoga|stretching|running|cycling|hiking|swimming|walking",
      "start_time": "ISO 8601 or relative",
      "duration_minutes": "int"
    }
  },
  {
    "name": "update_whoop_weight",
    "params": { "weight_lbs": "float (converted to kg server-side)" }
  },
  {
    "name": "set_whoop_alarm",
    "params": { "time": "HH:MM", "enabled": "bool" }
  },
  {
    "name": "delete_whoop_activity",
    "description": "Delete an activity from Whoop. Use whoop_activity_id from Workout model or list recent activities to find ID.",
    "params": { "activity_id": "string" }
  },
  {
    "name": "list_whoop_activities",
    "description": "List recent Whoop activities to find an activity ID for deletion or reference",
    "params": { "limit": "int (default 5)" }
  },
  {
    "name": "search_exercise_catalog",
    "params": { "query": "string (name, equipment, muscle group)" }
  }
]
```

### Coaching Rules (System Prompt)

**Verbosity scales with deviation:** GREEN + normal HRV + good sleep = don't mention Whoop, just coach. YELLOW with minor flags = brief mention. RED or significant deviations = full recommendation.

**Signal priority when conflicting:** sleep hours > HRV trend > daily recovery score > current strain.

**User override:** always respected without nagging. Acknowledge once, then coach at their selected intensity.

#### Personalized Rules (based on user's actual patterns)

**Yellow is baseline:**
This user's baseline recovery is yellow (50-65%). He benched 265x4 @RPE 7.5 on a 56% yellow day. Yellow days are full-send training days. Only flag recovery below 40% or consecutive reds.

**Sleep debt over sleep hours:**
User sleeps late (~2:30 AM), typically gets 6-7 hours. Don't flag under 7 hours. Flag only: under 5.5 hours, sleep debt increasing 3+ consecutive days, or short sleep before heavy bench day (needs 7+ for peak performance).

**RED = protect bench, sacrifice legs:**
Never skip bench days on RED. Suggest skipping/rescheduling legs or pull days first. If RED falls on bench day, reduce volume (fewer backoff sets) but keep top-end intensity.

**Heavy bench gating (weeks 4-5):**
- GREEN (67%+): proceed as programmed
- HIGH YELLOW (55-66%): proceed, monitor RPE on warmup sets. If 225 feels heavy (RPE 5+ instead of typical 3-4), suggest pulling back top weight 5-10 lbs
- LOW YELLOW (40-54%): open with warmups, assess at 225, user decides
- RED: strongly recommend rescheduling by 1 day. If user insists, cap at 90% of programmed top set
- 315 test day: only on GREEN/high-yellow (55%+), HRV within 15% of 7-day average, prior night 7+ hours sleep. Reschedule 1-3 days if conditions not met.

**Sauna strain excluded:**
Sauna adds ~3-5 strain points but is recovery, not training stress. If strain is high and a sauna was logged, subtract estimated sauna strain before making training adjustments.

**Caffeine timing:**
Caffeine before 4 PM is normal pre-training behavior. Only flag as sleep risk if consumed after 4 PM, especially before heavy bench days.

**RPE calibration across recovery:**
Same weight feels 0.5-1 RPE harder on yellow vs green. Normal, not regression. Only flag if RPE jumps AND recovery is similar (fatigue accumulation signal).

**Lower back monitoring:**
Track tension on barbell rows and trap bar deadlifts. If user reports tightness: don't increase weight, suggest bracing cues, check in about deadlift readiness on next leg day. If persistent across 2+ sessions, suggest machine/cable rows.

**Threshold calibration over time:**
These thresholds are starting points. As Claude observes patterns over sessions, it should calibrate. If user consistently trains well at 30% recovery, their functional RED zone is lower. Use RPE feedback as ground truth.

#### Generic Fallback Rules

For when personalized data is insufficient:

- Recovery < 34%: suggest lighter weights or recovery day, reduce volume ~20%, prioritize compounds
- Recovery 34-66%: follow program, monitor RPE, adjust if RPE runs 1+ higher than expected
- Recovery 67%+: full send, consider pushing intensity if RPE is low
- HRV drop > 15% below 7-day average: flag fatigue accumulation
- HRV sustained low 3+ days: recommend deload
- Sleep < 6 hours: lower volume, keep intensity, skip accessories
- Sleep < 5 hours: strongly suggest recovery day, minimum effective dose
- Strain > 18 before training: shorter session, main lifts only

### Mid-Session Adaptation

Claude combines RPE feedback with Whoop context to adjust weights between sets:

```
Set 1: Bench 275x3 @RPE 9
  Claude: "That moved hard. Recovery is yellow today.
  Let's drop to 265 instead of programmed 280."

Set 2: Bench 265x3 @RPE 7.5
  Claude: "Much better. Staying at 265 for remaining sets."
```

---

## Section 5: UX & Frontend Changes

### Principle

Whoop is ambient, not a feature. Woven into the existing experience, not bolted on as a separate panel.

### Profile Screen

**Disconnected state:**
- Value prop: "Connect to sync workouts, track recovery, and get coaching adjusted to your body."
- Single email/password form (Cognito)
- Password reassurance: "Password is used once to authenticate, then discarded."
- Whoop section collapsed for users who have never connected (one-line, tappable to expand)

**Connected state:**
- Connection status + last sync time (primary)
- Stats collapsed by default, expandable on tap for verification
- Sync Now and Disconnect buttons

**Migration state (one-time):**
- "Whoop auth has been upgraded. Please sign in again to reconnect."
- Replaces value prop, disappears after successful login

**First connection:**
- Foreground sync with loading state: "Syncing your Whoop data..."
- Stats populate after 2-3 seconds

### ContextBanner (3 states)

```
Normal:       ● GREEN 78%  | Bench Day | 820cal
Stale:        ● GREEN 78% (yesterday) | 820cal
Disconnected: ⚠ Whoop disconnected → tap to reconnect
```

Disconnected state is tappable — navigates directly to Profile login. One interaction, not a treasure hunt.

### Day Cards (history)

Only show sync indicator on failure/pending:
- Synced successfully: show nothing (success is the default)
- Pending: `↻ Whoop sync pending`
- Failed: `✗ Sync failed`

### Workout Completion

No new UI elements. Sync status is part of Claude's natural summary message.

### Progress Screen

Drop the proposed readiness composite chart. Instead, add sleep hours as a secondary line on the existing recovery chart. Don't invent a score when the raw signals are more useful. Recovery, HRV, and strain keep their own charts.

### First Workout with Whoop

One-time acknowledgment from Claude on the first workout after Whoop connection:
```
"I can see your Whoop data now — recovery is at 78%
 with solid HRV. I'll factor this into your training.
 Let's get after it."
```

### Diet Screen

No Whoop indicators. Trust the silent sync. One-time chat education handles awareness.

### SetCard

No changes. SetCard stays focused on weight, reps, RPE, rest timer. Coaching adjustments happen in chat text, not SetCard UI. This is the most time-sensitive UI — don't add data to it.

### Error Message Consistency

| Internal state | User-facing text | Where shown |
|-------|------|-------|
| WhoopAuthExpiredError | "Whoop disconnected" | Banner, Claude, Profile |
| WhoopRateLimitError | (silent, retry later) | Nowhere |
| WhoopAPIError | "Whoop sync issue" | Only if persistent |
| No token exists | "Connect Whoop" | Profile only |

Claude's prompt: "When Whoop errors occur, say 'Whoop is disconnected' and suggest checking the Profile tab. Don't use technical terms like authentication, token, or API."

### Components Changed

| Component | Change |
|-----------|--------|
| Profile screen | Remove OAuth, single Cognito login, collapsible stats, value prop |
| ContextBanner | Stale label, disconnected warning (tappable) |
| DayCard | Failure-only sync indicator |
| ProgressScreen | Sleep hours line on recovery chart |

### Components Unchanged

SetCard, RecoveryBanner, WorkoutDetail, ChatBubble, MealCard.

### Endpoints Removed

| Endpoint | Reason |
|----------|--------|
| GET /api/whoop/authorize | OAuth removed |
| GET /api/whoop/callback | OAuth removed |
| POST /api/whoop/test-write | No longer needed |

### Endpoints Modified

| Endpoint | Change |
|----------|--------|
| POST /api/whoop/login | Cognito auth (replaces old password login) |
| POST /api/chat | Tool-use loop for Whoop tools |
| POST /api/workout/complete | Auto-sync + exercise mapping |

### Frontend API Changes (api.ts)

- `whoopLogin(email, password)` — updated for Cognito (same shape, different backend)
- Remove: `whoopAuthorize()`, `whoopTestWrite()`
- Keep: `whoopStatus()`, `whoopLatest()`, `syncWhoop()`, `whoopDisconnect()`

### One-Time Message Tracking

Track via SystemMemory keys:
- `whoop_migration_shown` — auth upgrade notice (Profile)
- `whoop_journal_education_shown` — journal tracking explanation (chat)
- `whoop_first_workout_shown` — first workout acknowledgment (chat)

Clear all on disconnect, reset on reconnect.

---

## Data Model Changes

### Modified Tables

**WhoopToken:** `expires_at` already exists as `DateTime(nullable=True)`. No type change needed — convert to/from unix float at the `TokenSet` boundary in `get_whoop_client()`. Wipe existing OAuth token rows on migration.

**Meal:** Add `journal_signals` (JSON column, nullable, default null). Schema: `{"caffeine": int, "alcohol": bool}`. Late meal and protein computed from existing columns.

**Exercise:** Add `whoop_exercise_id` column (String, nullable). Claude populates it during workout planning via the exercise catalog search tool.

**WhoopSyncQueue:** Add `sync_type` column (String: "workout", "journal", "activity"). Make `workout_id` nullable.

**Workout:** Add `whoop_activity_id` column (String, nullable). Stores the Whoop activity UUID after successful sync. Used by `delete_whoop_activity` tool to resolve activity references.

### New Tables

**ExerciseCatalog:** Cached copy of Whoop's 310-exercise catalog.
- `whoop_id` (String, e.g. "BENCHPRESS_BARBELL")
- `name` (String)
- `equipment` (String, nullable)
- `muscle_group` (String, nullable)
- `cached_at` (DateTime)

### Removed

**SystemMemory rows:** `whoop_write_token`, `whoop_oauth_state`.

---

## Implementation Priority

```
P0 (foundation — everything depends on this):
  0. Initialize Alembic (alembic init, env.py for SQLite, initial schema migration)
  1. Migrate claude_service.py from CLI subprocess to Anthropic SDK (messages API)
  2. Claude tool-use loop in chat route (depends on #1)
  3. Cognito auth + client factory + whoop_operation() wrapper
  4. Alembic migration (Exercise.whoop_exercise_id, Workout.whoop_activity_id,
     ExerciseCatalog table, Meal.journal_signals, WhoopSyncQueue.sync_type)

P1 (core value):
  5. Workout auto-sync with exercise mapping
  6. Enhanced coaching rules in system prompt
  7. Smart sync triggers (app open, workout start, sync lock)

P2 (polish):
  8. Meal -> journal signal extraction + sync
  9. Ad-hoc Claude tools (sauna, weight, alarm, delete, list, catalog search)
  10. Frontend changes (Profile, ContextBanner, DayCard, Progress)

P3 (nice-to-have):
  11. Sleep hours on recovery chart
  12. One-time education messages (journal, first workout)
  13. Coaching threshold calibration over time
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| whoop-write-api v0.4 has undiscovered bugs | Medium | High | Already tested by user, spike before full implementation |
| Tool-use loop adds latency to chat | Medium | Medium | Max 3 iterations, 30s timeout |
| Cognito auth gets blocked by Whoop | Low | High | Old OAuth kept as disabled fallback |
| Exercise fuzzy matching wrong IDs | Medium | Low | Claude resolves during planning, not fuzzy match |
| Rate limiting on reverse-engineered API | Low | Medium | Soft 20/hr limit with warning |

## Files to Create/Modify

| Priority | File | Changes |
|----------|------|---------|
| P0 | alembic/ | NEW — Initialize Alembic, env.py for SQLite, initial migration |
| P0 | server/services/claude_service.py | Replace CLI subprocess with Anthropic SDK, tool-use loop, enhanced context assembly, coaching rules |
| P0 | server/services/whoop_service.py | get_whoop_client() factory, whoop_operation() wrapper, smart sync |
| P0 | server/routes/whoop.py | Cognito login, remove OAuth routes |
| P0 | server/models.py | Exercise.whoop_exercise_id, Workout.whoop_activity_id, ExerciseCatalog table, Meal.journal_signals, WhoopSyncQueue.sync_type |
| P0 | server/config.py | Remove whoop_client_id, whoop_client_secret, whoop_access_token. Whoop availability checked via WhoopToken table |
| P0 | alembic migration | Schema changes for all model updates |
| P1 | server/routes/workout.py | Auto-sync with DetailedExercise on complete |
| P1 | server/services/whoop_tools.py | NEW — tool handler dispatch |
| P2 | server/routes/chat.py | Journal signal extraction from meal parse |
| P2 | frontend/src/screens/profile.tsx | Cognito login, collapsible stats |
| P2 | frontend/src/components/context-banner.tsx | Stale label, disconnected state |
| P2 | frontend/src/components/day-card.tsx | Failure-only sync indicator |
| P2 | tests/test_whoop.py | Update mocks for v0.4, test tool dispatch |
