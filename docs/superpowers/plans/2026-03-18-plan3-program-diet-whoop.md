# Plan 3: Program Drill-Down + Diet Drill-Down + Whoop Auto-Sync

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Three independent features: program tab shows per-set detail, diet tab groups meals by day with itemized breakdowns, Whoop syncs automatically every 4 hours.

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite, React/TypeScript, systemd

**Spec:** `docs/superpowers/specs/2026-03-18-daily-chat-workout-diet-overhaul-design.md` — Sections 3, 4, 5

---

## Feature A: Program Tab Drill-Down (Tasks 1-2)

### Task 1: GET /api/program/week/{number} endpoint

New endpoint returns all days for a week with full set data. For completed days, queries Set table (with set_type, order, rpe). For upcoming days, returns exercise prescriptions from existing program parser.

Response includes `source: "logged" | "planned"` per day. Supplements existing GET /api/program.

### Task 2: Frontend program drill-down

Update program-day.tsx to show inline set detail when a day card is expanded. Completed days show warm-up sets dimmed, working sets with RPE dots (green=easy, blue=solid, orange=tough, red=max). Upcoming days show working set prescriptions only. Day summary line at top.

## Feature B: Diet Tab Drill-Down (Tasks 3-4)

### Task 3: GET /api/meals/day/{date} endpoint + meal items

New endpoint returns individual meals for a specific date (lazy load on expand). Update existing meal endpoints to return items field. Update the meal save in meals.py to accept items.

### Task 4: Frontend diet tab overhaul

Rewrite diet.tsx: macro progress with "remaining" + "Get meal ideas" CTA, trend charts moved up, today's meals with itemized display (items array or single-line fallback), previous days collapsed with lazy load, "Fix" button alongside delete.

## Feature C: Whoop Auto-Sync (Tasks 5-6)

### Task 5: server/cli.py + updated timer/service files

Create CLI entry point for whoop sync with dedup logic, auth error detection. Update deploy files for 4-hour schedule.

### Task 6: Install timer + chat route sync trigger

Install the updated timer. Add first-daily-chat sync trigger to chat route (async background task when today's WhoopData is missing).

## Task 7: Integration Test + Deploy
