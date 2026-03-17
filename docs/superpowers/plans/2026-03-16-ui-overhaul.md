# UI/UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan.

**Goal:** Transform SpotMe from unstyled scaffolding into a polished, dark-theme, chat-first workout PWA with onboarding, collapsible workout dashboard, and program history.

**Architecture:** Chat is the primary interface. Workout state renders as a collapsible bar above the chat. 3 bottom tabs (Workout, History, Profile). 5-screen swipe onboarding on first launch.

**Tech Stack:** React 19, TypeScript, CSS custom properties (no Tailwind), Vite PWA

**Spec:** `docs/superpowers/specs/2026-03-16-ui-overhaul-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `frontend/src/index.css` | Global dark theme, CSS variables, all component styles |
| `frontend/src/components/onboarding.tsx` | 5-screen swipe tutorial, localStorage gate |
| `frontend/src/components/bottom-nav.tsx` | 3-tab navigation (Workout, History, Profile) |
| `frontend/src/components/workout-bar.tsx` | Collapsible workout summary (current exercise, sets, timer, Whoop data) |
| `frontend/src/components/set-card.tsx` | Inline tappable set suggestion card for chat messages |
| `frontend/src/screens/workout.tsx` | Main screen: workout bar + chat + inline cards |
| `frontend/src/screens/history.tsx` | Program view with collapsible weeks + session cards |
| `frontend/src/screens/profile.tsx` | Settings, Whoop status, replay tutorial |

### Modified files
| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Rewrite: 3-tab routing, onboarding gate, new screen imports |
| `frontend/src/main.tsx` | Add `import './index.css'` |
| `frontend/src/components/chat-bubble.tsx` | Add Claude label, support inline set-card rendering |
| `frontend/src/components/rest-timer.tsx` | Add compact mode for workout bar display |
| `frontend/src/types.ts` | Add SetSuggestion, ProgramData, WeekData types |

### Unused after (delete imports, keep files)
- `screens/coach.tsx` → merged into `screens/workout.tsx`
- `screens/dashboard.tsx` → replaced by `screens/workout.tsx`
- `screens/workout-session.tsx` → replaced by `screens/workout.tsx`
- `screens/program.tsx` → replaced by `screens/history.tsx`
- `screens/progress.tsx` → replaced by `screens/history.tsx`

---

## Chunk 1: Foundation (CSS + types + nav)

### Task 1: Global CSS

**Files:** Create `frontend/src/index.css`, Modify `frontend/src/main.tsx`

- [ ] Create `index.css` with CSS custom properties and all component styles:
  - `:root` variables for color system
  - Base styles: body, *, scrollbar
  - `.app` container, `.offline-banner`
  - `.bottom-nav` with 3-tab layout
  - `.onboarding` swipe container and slides
  - `.workout-bar` collapsed and expanded states
  - `.chat-bubble.user`, `.chat-bubble.assistant` with Claude label
  - `.set-card` inline suggestion card
  - `.coach-screen`, `.messages`, `.input-bar`
  - `.history-screen`, `.program-header`, `.week-section`, `.session-card`
  - `.profile-screen`
  - Transitions and touch-action for swipe

- [ ] Add `import './index.css'` to `main.tsx` line 3

### Task 2: Type updates

**Files:** Modify `frontend/src/types.ts`

- [ ] Add types:
```typescript
export interface SetSuggestion {
  exercise: string
  weight: number
  reps: number
  basis?: string // "Based on last session + recovery"
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  setCard?: SetSuggestion
}

export interface SessionData {
  day: string
  type: string
  status: 'completed' | 'today' | 'upcoming'
  exercises?: string
  recovery?: number
  strain?: number
  duration?: number
}

export interface WeekData {
  number: number
  label: string
  sessions: SessionData[]
  completed: number
  total: number
}
```

### Task 3: Bottom nav component

**Files:** Create `frontend/src/components/bottom-nav.tsx`

- [ ] Create component with 3 tabs: Workout (dumbbell icon), History (list icon), Profile (gear icon)
- [ ] Props: `active: string`, `onChange: (tab: string) => void`
- [ ] Active tab highlighted with accent color

---

## Chunk 2: Onboarding

### Task 4: Onboarding component

**Files:** Create `frontend/src/components/onboarding.tsx`

- [ ] 5 slides: Welcome, Talk To It, It Learns, Quick Tips, Let's Go
- [ ] Touch swipe navigation using translateX transforms
- [ ] Dot indicators showing current position
- [ ] "Start Training" CTA on final slide sets `localStorage.spotme_onboarded = '1'` and calls `onComplete()`
- [ ] Props: `onComplete: () => void`

---

## Chunk 3: Core workout screen

### Task 5: Set card component

**Files:** Create `frontend/src/components/set-card.tsx`

- [ ] Props: `exercise: string`, `weight: number`, `reps: number`, `basis?: string`, `onStart?: () => void`
- [ ] Renders: "NEXT SET" label, weight x reps, basis text, orange "Start Set" button
- [ ] onStart callback triggers rest timer and logs set

### Task 6: Updated chat bubble

**Files:** Modify `frontend/src/components/chat-bubble.tsx`

- [ ] Add "CLAUDE" label for assistant messages
- [ ] Accept optional `setCard` prop, render `SetCard` inline when present
- [ ] Keep existing className pattern

### Task 7: Rest timer compact mode

**Files:** Modify `frontend/src/components/rest-timer.tsx`

- [ ] Add `compact?: boolean` prop
- [ ] Compact mode: just the countdown text, no button (for workout bar)
- [ ] Add `onComplete?: () => void` callback
- [ ] Export a `useRestTimer` hook for shared state between bar and chat

### Task 8: Workout bar

**Files:** Create `frontend/src/components/workout-bar.tsx`

- [ ] Collapsed: exercise name, set progress, rest timer, expand arrow
- [ ] Expanded: program name, Whoop recovery/HRV/RHR, exercise list (done/current/upcoming)
- [ ] Props: workout data, onCollapse toggle
- [ ] Tap to toggle collapsed/expanded

### Task 9: Workout screen

**Files:** Create `frontend/src/screens/workout.tsx`

- [ ] Merge coach.tsx chat functionality with workout bar
- [ ] Fetch today's workout on mount for workout bar data
- [ ] Chat sends to `/api/chat`, renders responses with inline set cards
- [ ] Parse Claude responses for set suggestions (JSON in response)
- [ ] Rest timer auto-starts when set logged
- [ ] Chat input with send button, placeholder text
- [ ] Scroll chat to bottom on new messages

---

## Chunk 4: History + Profile + App shell

### Task 10: History screen

**Files:** Create `frontend/src/screens/history.tsx`

- [ ] Segmented control: Program | Workouts | PRs
- [ ] Program view: header with name/phase/goal, progress bar, collapsible weeks
- [ ] Week sections: expanded for current week, collapsed for past
- [ ] Session cards: green=done, orange=today, gray=upcoming
- [ ] Completed sessions show exercise summary + Whoop data
- [ ] "GO" button on today's session navigates to Workout tab

### Task 11: Profile screen

**Files:** Create `frontend/src/screens/profile.tsx`

- [ ] Whoop connection status
- [ ] Sync Whoop button (calls api.syncWhoop)
- [ ] Replay tutorial button (clears localStorage, shows onboarding)
- [ ] App version

### Task 12: App.tsx rewrite

**Files:** Modify `frontend/src/App.tsx`

- [ ] Onboarding gate: check localStorage, show Onboarding if first launch
- [ ] 3-tab routing: 'workout' | 'history' | 'profile'
- [ ] Default to 'workout' tab
- [ ] Use BottomNav component
- [ ] Offline banner remains
- [ ] History tab's "GO" button switches to workout tab

---

## Chunk 5: Build + deploy

### Task 13: Build and verify

- [ ] Run `npm run build` in frontend/
- [ ] Verify no TypeScript errors
- [ ] Restart spotme service
- [ ] Test on phone via Tailscale HTTPS
