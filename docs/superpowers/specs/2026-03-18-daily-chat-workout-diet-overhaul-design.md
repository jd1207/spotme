# SpotMe UX Overhaul: Daily Chat, Workout Mode, Diet Drill-Down

**Date:** 2026-03-18
**Status:** Design approved, pending implementation

## Overview

Five interconnected changes that transform SpotMe from a basic chat-with-Claude workout app into a structured daily coaching system with server-side workout sequencing, day-based nutrition logging, and automatic biometric sync.

### Features

1. **Day-by-day persistent chats** — each day has its own conversation, today auto-opens, previous days accessible and interactive
2. **Workout mode with server-side sequencing** — explicit workout start triggers structured set-by-set flow with rest timers and real-time feedback
3. **Program tab drill-down** — two-level accordion showing per-set detail with warm-ups for completed days
4. **Diet tab day-based drill-down** — day-grouped meal log with itemized breakdowns and actionable meal suggestions
5. **Whoop auto-sync** — every 4 hours + on first daily chat, with auth failure surfacing

## 1. Day-by-Day Persistent Chats

### Problem

General chats (workout_id=null) pile into one undifferentiated bucket. No date grouping, no persistence between sessions, no way to view previous days' conversations.

### Data Model Changes

**Conversation model** — add `date` column:
```
date: String, YYYY-MM-DD, Eastern time, not null
```
Migration: backfill existing rows from `created_at` with Eastern timezone conversion. All new messages stamped with `datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")`.

Eastern timezone is stored as a named constant `TIMEZONE = ZoneInfo("America/New_York")` in a shared location (server/config.py).

### New Endpoints

**`GET /api/chat/days`** — returns list of recent days with summary stats:
```json
{
  "days": [
    {
      "date": "2026-03-18",
      "message_count": 8,
      "workout_type": "Volume Bench",
      "recovery_score": 79,
      "recovery_zone": "GREEN",
      "calories_total": 1850,
      "summary": "5x6 @ 235 bench · 1,850 cal"
    }
  ]
}
```
Summary is generated server-side from that day's workout data, set history, and meal totals.

**`GET /api/chat/day/{date}`** — returns all messages for that date, ordered by created_at. Includes messages from all workout_ids that share that date.

### Chat Route Changes

The existing `POST /api/chat` gets an optional `date` parameter (defaults to today Eastern). Context assembly for historical chats includes a note: `"Note: athlete is reviewing {date} on {today_date}."` so Claude knows it's retrospective.

All messages for a day are one stream. `workout_id` remains for backend context scoping but is not a frontend grouping mechanism.

### Frontend UX

**Default view: today's chat is open immediately.**

Header: "← Days" back button + today's date. Context banner below header:
```
┌─ context card ──────────────────┐
│ GREEN 79% Recovery              │
│ Volume Bench                    │
│ 1,850 / 3,200 cal              │
└─────────────────────────────────┘
```
Chat messages below. Input bar at bottom. Standard chat flow.

**"Days" back button opens the history list:**

Day cards show:
- Workout type as the headline (or "Rest Day")
- Recovery zone as a colored dot
- Key stats: top lifts for workout days, calorie total for rest days
- Date as secondary text

Today's card is at the top, prominent. Previous days below, tappable to open interactive chat for that day.

**Historical chat behavior:** Opening a previous day loads that day's messages. User can send new messages — they are stored with that day's date. Claude receives that day's workout/recovery context plus the note that the athlete is reviewing retrospectively.

## 2. Workout Mode with Server-Side Sequencing

### Problem

Claude's set_suggestion is unreliable — it guesses from context rather than tracking a sequence. The "next set" shown in chat is often wrong. No structured warm-up flow.

### Approach: Hybrid A+B

Claude generates the workout plan. The server stores and tracks it. Claude coaches and can modify the plan, but the server is the source of truth for what set is next.

### Data Model Changes

**Set model** — add columns:
```
target_weight: Float, nullable
target_reps: Integer, nullable
set_type: String ("warmup" | "working"), nullable
order: Integer, nullable
```

When a workout starts, planned sets are created with targets, set_type, order, and completed=False. When the user completes a set, actual weight/reps/rpe fill in and completed=True.

No new tables. Extends the existing Set model within the existing Exercise/Set hierarchy.

### Workout Activation

Two triggers:
1. **"Start Workout" button** in the context banner (primary, reliable)
2. **Natural language** — "starting my workout", "let's go" etc. (secondary, Claude interprets)

When activated:
1. Claude generates a `workout_plan` field in its response — ordered list of all sets (warm-up + working) for all exercises
2. Chat route creates Exercise and Set records with targets and order
3. Response includes `workout_active: true` and the first planned set
4. Frontend enters workout mode

**Claude's workout_plan response field:**
```json
"workout_plan": [
  {"exercise": "Bench Press", "set_type": "warmup", "weight": 135, "reps": 10},
  {"exercise": "Bench Press", "set_type": "warmup", "weight": 185, "reps": 5},
  {"exercise": "Bench Press", "set_type": "warmup", "weight": 225, "reps": 3},
  {"exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6},
  {"exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6},
  ...
]
```

**Fallback:** If Claude fails to return a plan, server generates a basic sequence from program_parser.py (working sets only, no warm-ups). Degraded but functional.

### Set Completion Flow

**Single API call:** `POST /api/workout/complete-set`

Request: `{ set_id, actual_weight, actual_reps, actual_rpe, feel: "easy"|"solid"|"tough"|"max" }`

Response:
```json
{
  "logged_set": { ... },
  "next_set": { "exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6, "set_number": 3, "order": 6 },
  "progress": { "completed": 5, "total": 18, "current_exercise_progress": "3 of 5" },
  "next_exercise_preview": "DB Flat Press 80x10"
}
```

Claude coaching fires async — coaching message appears in chat when ready, but the set card advances immediately. No waiting for Claude to tell you what's next.

### Mid-Workout Adjustments

User tells Claude "that felt heavy, drop to 225." Claude responds with coaching text and a `workout_plan` field containing a full replacement sequence for all remaining pending sets. Server replaces all pending Set rows. No surgical patch logic.

Skip: "Skip" button on set card marks the set as skipped and advances. "Bench is taken" via chat → Claude reorders remaining exercises.

### Set Card UX

The set card is a persistent sticky element above the input bar. It evolves in place — never disappears during a workout.

**State 1 — Next set:**
```
┌─────────────────────────────────┐
│ Bench Press — Warm-up 1 of 3   │
│ 135 x 10                       │
│                  [Skip]  [Done] │
└─────────────────────────────────┘
```

**State 2 — After "Done" (working sets only), collect feedback:**
```
┌─────────────────────────────────┐
│ Done — 235 x 6                  │
│ How'd that feel?                │
│ [Easy]  [Solid]  [Tough]  [Max] │
│                                 │
│ Rest 1:48         NEXT: 235 x 6 │
│              [+30s]  [Skip Rest] │
└─────────────────────────────────┘
```

Warm-up sets skip the feedback prompt and auto-advance to rest.

Feel buttons map to RPE: Easy→6.5, Solid→7.5, Tough→9, Max→10. Stored on the Set record's existing `rpe` field.

**State 3 — After tapping a feel button, rest mode:**
```
┌─────────────────────────────────┐
│ Done — 235 x 6 — Tough          │
│ Rest 1:32         NEXT: 235 x 6 │
│              [+30s]  [Skip Rest] │
└─────────────────────────────────┘
```

**Rest timer auto-adjusts by feel:** Easy→90s, Solid→120s, Tough→150s, Max→180s. User can override with +30s or Skip Rest.

**"Done" pre-fills from targets.** Tap weight or reps number to quick-edit before confirming (handles "I only got 4 reps").

**"View Plan" link** below the set card expands an overlay showing the full remaining sequence. Collapsible.

### Workout Completion

All sets completed or user says "done" → workout marked complete. Claude summarizes the session and updates training memory. Frontend exits workout mode, returns to chat.

## 3. Program Tab Drill-Down

### Problem

The program tab shows exercise names per day but no set-level detail — no weights, no warm-ups, no RPE history. You can't see what a completed workout actually looked like.

### Approach: Two-Level Accordion

Week → Day. No third level. When a day card expands, all exercises and sets are visible inline.

### Data Source

**Completed days:** Query Set table (which now has target_weight, target_reps, set_type, order). Real logged data with RPE.

**Upcoming days:** Parse from SystemMemory via program_parser.py. Working set prescription only ("Bench Press — 235 x 6 — 5 sets"). No warm-ups for upcoming days — warm-ups appear when the workout starts (Section 2).

### New Endpoint

**`GET /api/program/week/{number}`** — returns all days for a week with full set data.

Response includes `source: "logged" | "planned"` per day so the frontend renders appropriately.

### Expanded Day Card — Completed

```
Wednesday — Volume Bench                ✓
Total: 18 sets · Top set 235x6 · Avg feel: Solid

Bench Press
  135 x 10   warm-up
  185 x 5    warm-up
  225 x 3    warm-up
  235 x 6    ●       (green dot = solid)
  235 x 6    ●
  235 x 6    ●
  235 x 6    ◉       (orange dot = tough)
  235 x 4    ◉       (amber "4" = missed target of 6)

DB Flat Press
  80 x 10    ●
  80 x 10    ●
  80 x 8     ◉
```

- Warm-up sets: dimmed text, smaller font
- Working sets: full brightness, accent-colored weight
- RPE shown as colored dot: green (easy), blue (solid), orange (tough), red (max)
- Target miss: amber text on the reps number, no parenthetical
- Day summary line at top: total sets, top set, average feel

### Expanded Day Card — Upcoming

```
Friday — Heavy Bench
Bench Press — 265 x 4 — 3 sets
Pause Bench — 225 x 5 — 3 sets
Close Grip — 205 x 8 — 2 sets
```

Clean working set prescription. No warm-ups (they appear at workout time).

### Data Fetching

One API call per week expansion. Set data cached client-side. Exercise expansion is purely client-side rendering.

## 4. Diet Tab Day-Based Drill-Down

### Problem

The diet tab shows a flat list of today's meals with single-line descriptions that truncate. No way to see previous days. Descriptions like "chicken breast, rice, broccoli" are hard to scan. No actionable next step from the tab.

### Data Model Changes

**Meal model** — add `items` column:
```
items: Text, nullable (JSON-serialized array of strings)
```

Claude's meal response field updated to include items:
```json
"meal": {
  "description": "chicken breast, rice, broccoli",
  "items": ["200g chicken breast", "Cup of white rice", "Steamed broccoli"],
  "calories": 585, "protein": 66, "carbs": 49, "fat": 8,
  "meal_type": "lunch"
}
```

If `items` present, render as a list. If not (legacy data), show description as single line. Backwards compatible.

### Meal Card Header

Use `meal_type` if set, with `created_at` time as fallback. "Lunch · 12:30 PM" when both available. "12:30 PM" when meal_type is null. Update Claude's system prompt to consistently set meal_type.

### Diet Tab Layout

```
Diet

┌─ Macro Progress ───────────────┐
│ Calories   ████████░░ 1,850    │
│                    / 3,200     │
│ Protein    ██████░░░░ 120g     │
│                    / 200g      │
│ 180g carbs · 58g fat           │
│                                │
│ 1,350 cal · 80g protein to go  │
│              [Get meal ideas →] │
└────────────────────────────────┘

┌─ 7-Day Trends ─────────────────┐
│ ▁▃▅▇▆▅▃  cal    ▂▄▅▇▅▃▄  pro │
└────────────────────────────────┘

TODAY'S MEALS

┌────────────────────────────────┐
│ Lunch · 12:30 PM               │
│ · 200g chicken breast          │
│ · Cup of white rice            │
│ · Steamed broccoli             │
│ 585 cal · 66g protein          │
│                   [Fix]  [×]   │
├────────────────────────────────┤
│ Breakfast · 8:15 AM            │
│ · 3 large eggs                 │
│ · 2 slices toast               │
│ · Peanut butter (2 tbsp)      │
│ 560 cal · 32g protein          │
│                   [Fix]  [×]   │
└────────────────────────────────┘

PREVIOUS DAYS
┌────────────────────────────────┐
│ Yesterday — 2,800 cal · 195g P ▶│
│ Mon — 3,100 cal · 220g P       ▶│
│ Sun — 2,650 cal · 180g P       ▶│
└────────────────────────────────┘
```

### Key Behaviors

**"Get meal ideas"** opens chat pre-populated with remaining macro context: "I need 1,350 more calories and 80g protein to hit my targets — suggest a meal."

**"Fix" button** opens chat pre-populated with: "The [meal description] was actually..." — Claude re-estimates and the old record is replaced.

**Previous days** are collapsed by default. Tap to expand — triggers lazy fetch via `GET /api/meals/day/{date}`. Shows that day's meals in the same card format.

**Calories + protein are primary.** Carbs and fat shown only in the macro progress section, not repeated on every meal card.

### Endpoints

- `GET /api/meals/today` — unchanged, returns today's meals + totals
- `GET /api/meals/week` — unchanged, returns daily aggregates for trend charts
- `GET /api/meals/day/{date}` — **new**, returns individual meals for a specific date (lazy load on expand)

## 5. Whoop Auto-Sync

### Problem

The Whoop sync timer exists in deploy/ but is not installed or enabled. Manual sync required. Data didn't sync today.

### Sync Schedule

Every 4 hours: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00. Plus an immediate sync on first daily chat (so morning recovery is always fresh when you open the app).

Timer config:
```ini
[Timer]
OnCalendar=*-*-* 00,04,08,12,16,20:00:00
Persistent=true
```

~6 syncs/day. Conservative for a reverse-engineered API.

### Dedup Logic

Sync job checks last successful sync time (from WhoopData.synced_at). If <3 hours ago, skip. Prevents catch-up storms when Deck wakes from sleep.

### Entry Point

Replace the one-liner in the service file with a proper CLI command:
```
ExecStart=%h/spotme/.venv/bin/python -m server.cli whoop_sync
```

The `server/cli.py` module handles logging, dedup check, auth error detection, and graceful failure.

### Auth Failure Surfacing

If sync fails due to auth errors 3+ consecutive times:
- Set a flag in SystemMemory or a new status field
- Frontend recovery banner shows "Whoop disconnected — reconnect in Settings" instead of stale recovery data
- Profile tab Whoop section shows the error state

### UI Behavior

- **Normal state:** No sync timestamp shown. Recovery data just appears fresh in the context banner.
- **Stale data (>6 hours):** Subtle warning: "Recovery data may be outdated"
- **Auth failed:** "Whoop disconnected — reconnect in Settings"
- **Profile tab:** "Auto-syncing every 4 hours · Last: 11:00 AM" with a small "Sync Now" secondary action
- **First connection:** Immediate sync triggered on Whoop connect flow

### Installation

```bash
cp deploy/spotme-whoop-sync.timer ~/.config/systemd/user/
cp deploy/spotme-whoop-sync.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now spotme-whoop-sync.timer
```

## Cross-Cutting Concerns

### Timezone

All date logic uses Eastern time. Constant: `TIMEZONE = ZoneInfo("America/New_York")` in `server/config.py`. Frontend formats dates for display but the date string value is always Eastern-derived.

### Claude System Prompt Updates

- Add `workout_plan` field documentation to response format
- Add `items` array to meal field documentation
- Add `plan_adjustment` note (full replacement of remaining sets)
- Update profile fields to mention `calorie_target`, `protein_target` (already done)
- Instruct Claude to consistently set `meal_type`
- Add workout mode instructions: when user starts a workout, generate the full warm-up + working set sequence from training memory

### Migration

- Conversation: add `date` column, backfill from `created_at` with Eastern conversion
- Set: add `target_weight`, `target_reps`, `set_type`, `order` columns
- Meal: add `items` column
- All nullable, all idempotent ALTER TABLE (same pattern as existing calorie_target migration)

### File Size Constraint

200-line max per component file (per CLAUDE.md). New components will need to be split if they exceed this. The set card (with its 3 states + feedback + timer) will likely need to be its own component file.
