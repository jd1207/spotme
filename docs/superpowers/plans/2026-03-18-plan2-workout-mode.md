# Plan 2: Workout Mode with Server-Side Sequencing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When user starts a workout, Claude generates a full set sequence (warm-ups + working sets). Server stores and tracks it. A sticky set card walks the user through each set with feedback collection and adaptive rest timers.

**Architecture:** New `workout_sequencer.py` service owns set sequencing. `POST /api/workout/complete-set` advances the sequence. Claude's system prompt updated to output `workout_plan` arrays. Frontend `set-card.tsx` component handles the 3-state UX (next set → feedback → rest).

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-18-daily-chat-workout-diet-overhaul-design.md` — Section 2

**Test command:** `.venv/bin/python -m pytest -x --tb=short`
**Frontend build:** `cd frontend && npm run build`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `server/services/workout_sequencer.py` | Create | create_workout_from_plan, complete_set, get_next_set, replace_pending_sets |
| `server/schemas.py` | Modify | Add CompleteSetRequest, CompleteSetResponse |
| `server/routes/workout.py` | Modify | Add POST /workout/complete-set endpoint |
| `server/services/claude_service.py` | Modify | Update system prompt, extract workout_plan from response |
| `server/routes/chat.py` | Modify | Detect workout_plan, call sequencer, return workout_active + current_set |
| `tests/test_sequencer.py` | Create | Tests for workout_sequencer service |
| `tests/test_complete_set.py` | Create | Tests for complete-set endpoint |
| `frontend/src/api.ts` | Modify | Add completeSet, getWorkoutPlan API methods |
| `frontend/src/components/set-card.tsx` | Create | Sticky set card with 3 states |
| `frontend/src/screens/workout.tsx` | Modify | Integrate set card into workout mode |
| `frontend/src/types.ts` | Modify | Add PlannedSet, WorkoutPlan types |
| `frontend/src/index.css` | Modify | Set card styles |

---

## Task 1: Workout Sequencer Service

**Files:**
- Create: `server/services/workout_sequencer.py`
- Create: `tests/test_sequencer.py`

The sequencer has 4 functions:
- `create_workout_from_plan(db, plan, date, workout_type)` — creates Workout + Exercise + Set records from Claude's plan array
- `complete_set(db, set_id, actual_weight, actual_reps, actual_rpe, feel)` — marks set done, returns next
- `get_next_set(db, workout_id)` — returns first pending set
- `replace_pending_sets(db, workout_id, new_plan)` — replaces remaining planned sets

Feel-to-RPE mapping: easy=6.5, solid=7.5, tough=9.0, max=10.0

Set model fields used: weight/reps (pre-filled from targets, overwritten on completion), target_weight, target_reps, set_type ("warmup"/"working"), order (int), status ("pending"/"completed"/"skipped"), completed (bool, for backwards compat), rpe.

- [ ] **Step 1: Write tests**
- [ ] **Step 2: Run tests, verify fail**
- [ ] **Step 3: Implement workout_sequencer.py**
- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Run full suite**
- [ ] **Step 6: Commit**

---

## Task 2: Complete-Set Endpoint

**Files:**
- Modify: `server/schemas.py`
- Modify: `server/routes/workout.py`
- Create: `tests/test_complete_set.py`

New endpoint: `POST /api/workout/complete-set`

Request schema `CompleteSetRequest`: set_id (int), actual_weight (float), actual_reps (int), actual_rpe (float|None), feel (str|None: "easy"|"solid"|"tough"|"max")

Response: `{ logged_set, next_set, progress: { completed, total, current_exercise_progress }, next_exercise_preview }`

Calls `workout_sequencer.complete_set()` internally.

- [ ] **Step 1: Write tests**
- [ ] **Step 2: Run tests, verify fail**
- [ ] **Step 3: Add schema + endpoint**
- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Run full suite**
- [ ] **Step 6: Commit**

---

## Task 3: Claude System Prompt + ClaudeService Updates

**Files:**
- Modify: `server/services/claude_service.py`

Updates to SYSTEM_PROMPT:
1. Add `workout_plan` field to Response Format docs
2. Add `items` array to meal field docs
3. Add instruction: "When user mentions daily nutrition targets, set calorie_target and protein_target"
4. Add instruction: consistently set `meal_type` on meal responses
5. Add Workout Mode section explaining when to generate workout_plan

Updates to ClaudeService.chat():
1. Extract `workout_plan` from parsed response (add to return dict)
2. Extract `items` from meal field

- [ ] **Step 1: Update SYSTEM_PROMPT**
- [ ] **Step 2: Update ClaudeService.chat() return dict**
- [ ] **Step 3: Run full test suite**
- [ ] **Step 4: Commit**

---

## Task 4: Chat Route — Workout Plan Integration

**Files:**
- Modify: `server/routes/chat.py`
- Modify: `server/schemas.py`

When Claude returns `workout_plan`:
1. Call `create_workout_from_plan(db, plan, request_date)`
2. Get the first set via `get_next_set(db, workout_id)`
3. Return `workout_active: true` and `current_set` in ChatResponse

Update ChatResponse to include:
```python
workout_active: bool = False
current_set: dict | None = None
workout_id: int | None = None
```

Also handle `workout_plan` during mid-workout adjustments (replace_pending_sets).

Also save `items` from meal data if present.

- [ ] **Step 1: Update ChatResponse schema**
- [ ] **Step 2: Update chat route to handle workout_plan**
- [ ] **Step 3: Update meal save to include items**
- [ ] **Step 4: Run full test suite**
- [ ] **Step 5: Commit**

---

## Task 5: Frontend — Types + API Methods

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

Add types:
```typescript
export interface PlannedSet {
  id: number
  exercise: string
  set_type: 'warmup' | 'working'
  weight: number
  reps: number
  set_number: number
  order: number
}

export interface SetProgress {
  completed: number
  total: number
  current_exercise_progress: string
}
```

Update ChatResponse type to include `workout_active`, `current_set`, `workout_id`.

Add API methods:
- `completeSet(data)` — POST /workout/complete-set
- `getWorkoutPlan(workoutId)` — GET /workout/{id}/plan (returns remaining sets)

- [ ] **Step 1: Add types**
- [ ] **Step 2: Add API methods**
- [ ] **Step 3: Update ChatResponse type**
- [ ] **Step 4: Build frontend**
- [ ] **Step 5: Commit**

---

## Task 6: Frontend — Set Card Component

**Files:**
- Create: `frontend/src/components/set-card.tsx`
- Modify: `frontend/src/index.css`

Three states:
1. **Next set**: exercise name, set type + number, weight x reps, [Skip] [Done]
2. **Feedback** (working sets only): "How'd that feel?" [Easy] [Solid] [Tough] [Max] + rest timer + next preview
3. **Rest**: "Done — weight x reps — feel" + countdown + next preview + [+30s] [Skip Rest]

Rest durations: easy=90s, solid=120s, tough=150s, max=180s
Warm-ups skip feedback, go straight to rest (90s default).

Props: currentSet (PlannedSet), nextPreview (string), progress (SetProgress), onComplete (callback), onSkip (callback)

- [ ] **Step 1: Create set-card.tsx**
- [ ] **Step 2: Add CSS**
- [ ] **Step 3: Build frontend**
- [ ] **Step 4: Commit**

---

## Task 7: Frontend — Integrate Set Card into Workout Mode

**Files:**
- Modify: `frontend/src/screens/workout.tsx`

When ChatResponse returns `workout_active: true`:
1. Store `workoutId` and `currentSet` in state
2. Show set card as sticky element above input bar
3. "Done" on set card → call `api.completeSet()` → update currentSet from response
4. "Skip" → call completeSet with skipped flag
5. When all sets done (next_set is null), show completion message
6. Chat still works alongside — Claude coaching appears in messages

- [ ] **Step 1: Add workout mode state**
- [ ] **Step 2: Integrate set card rendering**
- [ ] **Step 3: Wire up complete/skip handlers**
- [ ] **Step 4: Build frontend**
- [ ] **Step 5: Commit**

---

## Task 8: Integration Test + Deploy

- [ ] **Step 1: Run full backend test suite**
- [ ] **Step 2: Build frontend**
- [ ] **Step 3: Restart service**
- [ ] **Step 4: Push**
