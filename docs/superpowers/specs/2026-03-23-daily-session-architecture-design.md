# Daily Session Architecture

## Problem

Every `/api/chat` request spawns a fresh `claude --print` subprocess (227MB binary, 2-5s startup, 100-200MB RAM). With Whoop tools connected, a single message spawns up to 3 sequential processes. Context (~4000 tokens) is rebuilt and re-sent on every call.

Stale CLI sessions accumulate on disk: **211 session files (84MB)** in `~/.claude/projects/-home-deck-spotme/` alone, 587MB total across all projects. The current code uses `--print` without `--no-session-persistence`, so every API call creates a new session file that is never cleaned up.

The app uses the Claude Code subscription (not an API key), so the Anthropic Python SDK is not an option. All Claude communication must go through the CLI.

## Verified CLI Behaviors

Tested on Claude CLI 2.1.81:

| Flag combo | Behavior | Verified |
|-----------|----------|----------|
| `--print --session-id <uuid> -p "msg"` | Creates a session with known UUID, saves to disk | Yes |
| `--print --resume <uuid> -p "msg"` | Resumes session, Claude remembers prior messages | Yes |
| `--print --no-session-persistence -p "msg"` | Responds without saving session file | Yes |
| `--output-format stream-json --verbose --print` | Streams JSONL events (requires `--verbose`) | Yes |
| `--tools ""` | Disables all built-in tools (we handle tools ourselves) | Yes |
| `--bare` | Skips hooks, LSP, auto-memory, CLAUDE.md — but breaks OAuth | Yes (unusable) |

Session files live at: `~/.claude/projects/-home-deck-spotme/<uuid>.jsonl`
No `sessions rm` CLI command exists — cleanup must delete files directly.

## Design

### One session per day

A single Claude CLI session per day. The session ID (a UUID) and its creation date are stored in `SystemMemory(key="active_session")` as JSON.

**First message of the day:**
```bash
claude --print \
  --session-id <new-uuid> \
  --tools "" \
  --model claude-sonnet-4-20250514 \
  --append-system-prompt "$SYSTEM_PROMPT" \
  -p "$CONTEXT_BLOCK\n\n$USER_MESSAGE"
```
Creates a persistent session with full context (system prompt, training plan, whoop data, profile, last 15 training log entries including yesterday's daily summary, today's meals).

**Subsequent messages:**
```bash
claude --print \
  --resume <session-uuid> \
  --tools "" \
  -p "$USER_MESSAGE"
```
Resumes the session. Only the new user message is sent — Claude already has context from the session. If whoop data or meal totals changed since the last message, prepend a brief update.

**No persistent processes**: each CLI invocation exits after responding. Session state lives on disk as a JSONL file managed by the CLI.

### Daily handoff

Triggered on the first message after 4 AM Eastern when a session from a previous day exists.

1. Resume the old session with a summary prompt:
   ```
   claude --print --resume <old-uuid> --tools "" \
     -p "Summarize today's coaching session in 2-3 sentences. Include: what was trained, key performance notes, any program adjustments discussed, and anything to carry forward to tomorrow."
   ```
2. Save the summary as a `TrainingLog` entry with `log_type="daily_summary"`.
3. Delete the old session file: `rm ~/.claude/projects/-home-deck-spotme/<old-uuid>.jsonl`
4. Create a new session with fresh context (which now includes the summary in the last 15 log entries).
5. Update `SystemMemory(key="active_session")` with the new session ID and date.

If the old session is corrupted or the CLI fails to resume it, skip the summary and create a fresh session from DB state. The training plan and training log are the durable source of truth — the session is a disposable cache.

### Concurrency guard

Session continuity introduces ordering requirements. Two concurrent requests resuming the same session would race or fork the conversation.

```python
_session_lock = asyncio.Lock()

async def _call_claude_session(...):
    async with _session_lock:
        # only one CLI call at a time per session
        ...
```

This is acceptable for a single-user app. Concurrent taps queue behind the lock rather than spawning parallel processes.

### Tool-use: 2 calls max

Current state: up to 3 blind subprocess spawns per tool request, each re-sending full context with no memory of prior calls.

New state: tools execute within the session.

```
Call 1: claude --print --resume <session-uuid> --tools "" -p "user message"
  → Response includes tool_calls → server executes them

Call 2: claude --print --resume <session-uuid> --tools "" -p "Tool results: {results}"
  → Claude responds with confirmation
```

If no tool_calls in the response, it's just 1 call. Both calls share session context so Claude knows the original user message when processing tool results.

The text-based tool description approach stays in the system prompt (native tool-use requires the SDK). Reliability improves because Claude has full conversation context across tool iterations instead of a stateless follow-up.

### Streaming for chat

Chat responses use `--output-format stream-json --verbose` instead of `--print`. The server parses the JSONL stream and pipes `assistant` events to the frontend as SSE.

**Stream event format** (from testing):
```jsonl
{"type":"system","subtype":"init",...}
{"type":"assistant","message":{"content":[{"type":"text","text":"..."}],...}}
{"type":"result","subtype":"success",...}
```

The server filters for `type=assistant` events and extracts the text content.

**Backend:**
```python
# FastAPI StreamingResponse
async def stream_chat(...):
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print", "--resume", session_id,
        "--output-format", "stream-json", "--verbose",
        "--tools", "", "-p", message,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    # yield SSE events as assistant text arrives
```

**Frontend:** `fetch` with `ReadableStream` (not `EventSource`, which doesn't support POST).

**Tool-action follow-ups** use `--print` (non-streaming) since the response is short. The frontend displays the streamed first response, then appends the tool confirmation as a second message.

### Context diet

With session continuity, most context is sent once per day instead of every message.

| Data | First message of day | Subsequent messages |
|------|---------------------|-------------------|
| System prompt | Full (~1900 tokens) | In session |
| Training program | Full (~660 tokens) | In session |
| Profile | Full (~100 tokens) | In session |
| Yesterday's summary | Yes (~50 tokens) | In session |
| Whoop biometrics | Today's data | Only if refreshed |
| Meal totals | Current | Only if new meal logged |
| Training log (last 15) | Full | In session |
| Conversation history | Not needed | In session |
| New user message | Yes | Yes |

Estimated context per call: ~4000 tokens (first) → ~100-200 tokens (subsequent).

### Unblock concurrent updates

Remove the guard that blocks `memory_update` when `training_log_entry` is present (`chat.py` line 198). Claude should be able to both log a workout completion and adjust next week's program in the same response.

Add a safety check instead: if `memory_update` is present, diff it against the current training plan. If it's significantly shorter (>50% reduction), log a warning and keep the old version. This prevents accidental truncation without blocking legitimate updates.

### Session recovery

If `claude --print --resume <session_id>` fails (corrupted session, CLI update, missing file):

1. Log the error.
2. Delete the broken session file.
3. Create a new session with full context from DB.
4. Continue as if it's the first message of the day.

The training plan and training log are the source of truth. The session is a convenience layer — losing it means one slower request while context is rebuilt, not data loss.

### Initial cleanup

On first deploy, delete all existing stale sessions:
```bash
rm -f ~/.claude/projects/-home-deck-spotme/*.jsonl
```
This reclaims 84MB immediately. Going forward, only 1 session file exists at a time.

## Files to change

### Backend

| File | Change |
|------|--------|
| `server/services/claude_service.py` | Replace `_call_claude()` with session-aware `_call_claude_session()`. Add `_get_or_create_session()`, `_handoff_session()`, `_stream_claude_session()`. Replace `_call_claude_with_tools()` with 2-call session pattern. Add `asyncio.Lock` for concurrency. Keep `_call_claude()` with `--no-session-persistence` for stateless calls (interview questions, form analysis). Keep `_extract_json()` for `--print` responses. |
| `server/routes/chat.py` | Update `chat()` to use session-aware service. Add `GET /api/chat/stream` SSE endpoint. Remove the `memory_update` + `training_log_entry` mutual exclusion guard. Add length-based safety check for memory updates. |
| `server/models.py` | No new models. `SystemMemory(key="active_session")` stores `{"session_id": "...", "date": "2026-03-23"}` as JSON. |
| `server/config.py` | Add `SESSION_ROLLOVER_HOUR = 4` constant. |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/api.ts` | Add `chatStream()` method using `fetch` with `ReadableStream` for SSE parsing. |
| `frontend/src/screens/workout.tsx` | Update `send()` to use streaming. Append tokens incrementally to the assistant message. Fall back to non-streaming on error. |

### Cleanup

| File | Change |
|------|--------|
| `server/routes/video.py`, `server/routes/layout.py` | Remove stale `api_key=settings.anthropic_api_key` arguments from `ClaudeService()` calls. |
| Deploy script | One-time: `rm -f ~/.claude/projects/-home-deck-spotme/*.jsonl` |

## What stays the same

- System prompt content and structure (coaching rules, response format, tool behavior)
- All database models and schemas
- Training plan stored as markdown in SystemMemory
- TrainingLog append-only pattern
- Whoop integration (lazy imports, try/except, graceful degradation)
- Frontend component structure and layout system
- PWA offline capabilities
- `generate_interview_questions()` and `analyze_form()` remain stateless (`--print --no-session-persistence`)

## Risks

| Risk | Mitigation |
|------|-----------|
| `--resume` may not work with `--append-system-prompt` | Test first. Fallback: embed system prompt in first user message as a `[SYSTEM]` block. |
| `--output-format stream-json` requires `--verbose` (extra noise) | Filter events server-side, only forward `type=assistant` to frontend. |
| CLI update breaks session file format | Session recovery rebuilds from DB. No data loss. |
| Daily summary quality varies | Summary is additive (training log entry). Raw log entries still carry the facts. |
| Concurrent rapid taps | `asyncio.Lock` queues requests. Second tap waits for first to complete. |
| Session file grows very large after many messages | Monitor. If needed, trigger mid-day rollover at a message count threshold. |

## Success criteria

- Only 1 session file on disk at any time (down from 211)
- Chat responses begin streaming within 3-5 seconds (after CLI startup)
- Tool-use completes in 2 CLI calls, not 3
- Context sent per message drops from ~4000 to ~200 tokens after first message
- Claude remembers earlier conversations within the same day without re-sending history
- Program adjustments from feedback persist across days via training log
- No RAM bloat from orphaned processes
- 84MB of stale session files reclaimed on deploy
