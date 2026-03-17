# SpotMe UI/UX Overhaul Design Spec

## Context

SpotMe has a solid backend (FastAPI + Claude API + Whoop) and well-architected frontend scaffolding (React 19 + TypeScript + Vite PWA), but zero visual design — no CSS, stub screens, no onboarding. The user's primary workflow is conversational: chatting with Claude to log sets, get suggestions, and receive coaching. The UI needs to wrap around that chat-first experience.

## Design Decisions

- **Chat-centric with collapsible workout dashboard** — compact summary bar at top showing current exercise, set count, and rest timer. Tap to expand full workout overview. Below: full-width chat.
- **3 bottom tabs** — Workout (chat + cards), History (program + workouts + PRs), Profile (settings, Whoop, goals)
- **5-screen swipe onboarding** — shown once on first launch, stored in localStorage
- **Dark theme only** — gym-first, OLED-friendly, no light mode toggle
- **Inline action cards** — Claude's responses include tappable set cards, rest timers, exercise summaries

## Color System

```
Background:    #0a0a0a (deep dark, near-black)
Surface 1:     #1e1e1e (cards, chat bubbles)
Surface 2:     #252525 (elevated cards within messages)
Border:        #2c2c2c
Text primary:  #e0e0e0 (off-white)
Text secondary:#888888
Text disabled: #555555
Accent:        #ff6b35 (SpotMe orange)
Success:       #4CAF50
Info:          #4A90D9
Nav inactive:  #666666
```

## Screen 1: Workout (Main Screen)

### Collapsed state (default)
- Top bar: current exercise name (orange, bold) | set progress ("Set 3 of 4") | rest timer countdown (green) | expand arrow
- Below: full-width chat interface
- Chat input: rounded pill input with send button, placeholder "Tell Claude how that set felt..."

### Expanded state (tap top bar)
- Program name and rest timer in header
- Whoop recovery/HRV/RHR row (colored dots)
- Exercise list: completed (green border, strikethrough, checkmark), current (orange border, set progress), upcoming (gray border, dimmed)
- Tap to collapse back

### Chat behavior
- User messages: orange background, right-aligned, rounded bubbles
- Claude messages: dark surface background, left-aligned, "CLAUDE" label in orange
- Inline set cards within Claude messages: dark elevated card showing "NEXT SET", weight x reps, provenance text ("Based on last session + recovery"), orange "Start Set" button
- Rest timer auto-starts when a set is logged via chat or card tap

### Interaction flow
1. User chats: "225 for 5, felt easy"
2. Claude responds with text + inline set card suggesting next weight/reps
3. User taps "Start Set" to confirm or adjusts values, or just chats back
4. Rest timer runs in collapsed bar
5. Repeat

## Screen 2: History Tab

### Top segmented control
Three segments: **Program** | **Workouts** | **PRs**

### Program view (default)
- Program header: name, phase, week progress ("Week 6 of 8"), goal badge
- Progress bar showing percent through program
- Collapsible week sections:
  - Current week: expanded by default, shows session cards
  - Past weeks: collapsed, showing completion count ("4/4 checkmark" or "3/4")
  - Tap to expand any week

### Session cards within weeks
- Green left border + checkmark: completed session with exercise summary, Whoop data (recovery, strain, duration)
- Orange left border + "GO" button: today's session, tap to jump to Workout tab
- Gray left border, dimmed: upcoming/scheduled sessions
- Tap completed session to expand full exercise breakdown

### Workouts view
- Chronological list of all completed workouts, most recent first
- Each card: date, type, duration, exercise count, Whoop recovery

### PRs view
- List of personal records by exercise
- Each entry: exercise name, weight x reps, date achieved, trend indicator

## Screen 3: Profile Tab

- User settings: name, training preferences
- Whoop connection status and sync trigger
- Goal editor
- Equipment profile
- "Replay tutorial" button
- App version

## Onboarding (5 swipe screens)

Shown once on first launch. Stored in localStorage (`spotme_onboarded`). Re-accessible from Profile tab.

### Screen 1: Welcome
- SpotMe logo/icon, tagline "Your AI Training Partner"
- One-line description: "An AI coach that learns how you train, adapts to your body, and gets smarter every session."

### Screen 2: Talk To It
- "HOW IT WORKS" label
- "Just talk to Claude" headline
- Example chat bubbles showing natural conversation: logging sets, asking for suggestions

### Screen 3: It Learns
- "GETS SMARTER" label
- "Every session makes it better" headline
- Three feature cards: adapts weight suggestions (based on RPE), reads recovery (Whoop HRV + sleep), remembers preferences

### Screen 4: Quick Tips
- "PRO TIPS" label
- Four numbered tips: say how it felt, ask anything, override anytime, check the top bar

### Screen 5: Let's Go
- "Ready to train" headline
- Description: start by telling Claude what to work on, or let it suggest
- Orange "Start Training" CTA button → dismisses onboarding, shows Workout tab

### Shared elements
- Dot progress indicator at bottom of each screen (current dot orange, others gray)
- Swipe gesture to navigate between screens
- Skip option accessible but not prominent

## Component Architecture

### New components needed
- `onboarding.tsx` — swipe tutorial container with 5 slides
- `workout-bar.tsx` — collapsible workout summary bar (collapsed/expanded states)
- `set-card.tsx` — inline tappable set suggestion card within chat messages
- `program-view.tsx` — collapsible program/week/session hierarchy
- `bottom-nav.tsx` — 3-tab navigation bar
- `segmented-control.tsx` — tab switcher for History sub-views

### Modified components
- `App.tsx` — replace 5-tab nav with 3-tab, add onboarding gate
- `chat-bubble.tsx` — support inline components (set cards, timers) within messages
- `rest-timer.tsx` — compact mode for workout bar, auto-start on set log
- `layout-renderer.tsx` — may need updates to render inline cards within chat

### Removed/replaced
- `coach.tsx` screen — merged into Workout tab (chat is the main workout interface)
- `dashboard.tsx` screen — replaced by Workout tab
- `workout-session.tsx` screen — replaced by Workout tab
- `program.tsx` screen — replaced by History tab > Program view
- `progress.tsx` screen — replaced by History tab > PRs view

## CSS Architecture

Global stylesheet at `frontend/src/index.css` with CSS custom properties for the color system. No CSS modules, no Tailwind — plain CSS with semantic class names matching component names. Mobile-first, single breakpoint.

```css
:root {
  --bg: #0a0a0a;
  --surface-1: #1e1e1e;
  --surface-2: #252525;
  --border: #2c2c2c;
  --text-primary: #e0e0e0;
  --text-secondary: #888;
  --text-disabled: #555;
  --accent: #ff6b35;
  --success: #4caf50;
  --info: #4a90d9;
}
```

## Offline behavior

- Chat input queues messages to IndexedDB when offline, syncs on reconnect
- Workout bar shows last cached state
- History tab loads from cached data
- Subtle offline banner at top: "Offline — sets will sync when connected"

## What's NOT in scope

- Light mode
- Charting/graphing (PRs view is list-based for now)
- Video form check UI (existing hook stays, no new UI)
- Program creation/editing (Claude handles this via chat)
- Push notifications
