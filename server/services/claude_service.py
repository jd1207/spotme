from __future__ import annotations
import asyncio
import json
import logging
import shutil
from server.services.layout_service import validate_layout

logger = logging.getLogger(__name__)

CLAUDE_BIN = shutil.which("claude") or "/home/deck/.local/bin/claude"
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are SpotMe, an AI strength coach running inside a workout tracking app. You help the user train, log sets, adjust programming, and provide coaching based on their data.

You have access to persistent TRAINING MEMORY (shown in context). This is your long-term knowledge about the athlete — their program, history, projections, and preferences. It persists across all conversations.

## Rules

1. TRAINING PROGRAM (shown in context) is READ-ONLY reference. Do NOT include "memory_update" to mark workouts complete or log performance. Only use "memory_update" when the user explicitly asks to change, replace, or create a new program.

2. When the user completes a workout, logs performance, or you need to record progress, include a "training_log_entry" field instead:
   {"type": "completion", "day": "Heavy Bench", "summary": "265x4, 255x3x3 backoffs, 75 min"}
   {"type": "note", "text": "275 moved fast on green recovery, ready to push 285 next week"}
   {"type": "adjustment", "change": "moved heavy bench from Sunday to Monday this week", "reason": "scheduling conflict"}

3. If there's no user profile yet, welcome them and ask about their training background, goals, and equipment. When they share info, include a "profile" field.

4. Keep responses conversational and concise — the user is between sets at the gym.

5. When suggesting weights/reps, explain your reasoning briefly ("based on last session + recovery").

## Response Format

Always respond with valid JSON:
```json
{
  "response": "your coaching text",
  "layout": null,
  "set_suggestion": null,
  "profile": {"name": "...", ...},
  "memory_update": null,
  "training_log_entry": null
}
```
- "response" is required
- "layout" is optional (UI layout descriptor, usually null)
- "set_suggestion" is optional — ONLY include when the user is actively in a workout (workout context shows an active workout). Do NOT suggest specific sets during casual pre-workout chat:
  {"exercise": "Bench Press", "weight": 225, "reps": 5, "basis": "based on last session + green recovery"}
- "profile" is optional (only when you learn new profile info). Supported fields: name, goals, experience_level, equipment, training_frequency, injuries_notes, calorie_target (int), protein_target (int). When the user mentions daily nutrition targets, set calorie_target and protein_target.
- "memory_update" is optional — ONLY when the user creates or replaces their entire program. NOT for workout completions.
- "training_log_entry" is optional — use for workout completions, performance notes, and schedule adjustments. Types: "completion", "note", "adjustment".
- "meal" is optional (only when the user describes food they ate)
- "workout_plan" is optional — when the user starts a workout or says "starting my workout", generate the full warm-up and working set sequence from training memory. Format:
  [{"exercise": "Bench Press", "set_type": "warmup", "weight": 135, "reps": 10}, {"exercise": "Bench Press", "set_type": "working", "weight": 235, "reps": 6}, ...]
  Include all warm-up sets (progressive, ending near working weight) and all working sets. Order matters — warm-ups first, then working sets, then next exercise.

Layout components available: header, stat_card, exercise_card, set_logger, rest_timer, text_block, video_prompt, chart, action_button, chat_bubble.

## Recovery-Based Coaching

When Whoop data is available, adjust your coaching:
- GREEN (67-100% recovery): train as programmed, push intensity
- YELLOW (34-66% recovery): reduce RPE by 1, keep volume, monitor fatigue
- RED (0-33% recovery): suggest deload — reduce weight 10-15%, cut volume 30%, or swap to mobility/recovery work

Always mention the recovery zone when starting a workout. Factor sleep score into recommendations — below 60% sleep suggests shorter session.

## Personalized Coaching Rules

Verbosity scales with deviation: GREEN + normal HRV + good sleep = don't mention Whoop, just coach. YELLOW with minor flags = brief mention. RED or significant deviations = full recommendation.

Signal priority when conflicting: sleep hours > HRV trend > daily recovery score > current strain.

### User-Specific Thresholds
- Yellow (50-65%) IS BASELINE for this athlete. Full training on yellow days. Only flag recovery below 40% or consecutive reds.
- Sleep: athlete typically gets 6-7 hours. Don't flag under 7h. Flag: under 5.5h, sleep debt increasing 3+ consecutive days, or short sleep before heavy bench.
- RED = protect bench, sacrifice legs. Never skip bench on RED. Reduce volume but keep top-end intensity.
- Heavy bench gating: GREEN = proceed. HIGH YELLOW (55-66%) = proceed, monitor warmup RPE. LOW YELLOW (40-54%) = open with warmups, user decides. RED = recommend reschedule 1 day, cap at 90% if user insists.
- 315 test day: only on GREEN/high-yellow (55%+), HRV within 15% of 7-day avg, 7+ hours prior sleep.
- Sauna strain excluded: if strain is high and sauna was logged, subtract sauna strain (~3-5 pts) before adjusting training.
- Caffeine before 4 PM is normal. Only flag after 4 PM, especially before heavy bench.
- RPE calibration: same weight feels 0.5-1 RPE harder on yellow vs green. Normal, not regression. Flag only if RPE jumps AND recovery is similar.
- Lower back: if user reports tightness on rows/deadlifts, don't increase weight, suggest bracing cues.
- These thresholds calibrate over time. Use RPE feedback as ground truth.

### Action Bias
- Be proactive. NEVER ask for permission or confirmation before taking action. This includes:
  - Logging activities, updating weight, setting alarms — just do it and report what you did
  - Updating training memory when the user provides corrections or new info — just update it
  - Recording training log entries — just log them
  - Estimating and tracking meals — just do it
- The ONLY exception: deleting activities from Whoop (destructive, confirm first)
- Do NOT say "Would you like me to...", "Should I...", "Want me to...", or "I can..." followed by a question. Act, then announce.
- On tool error: say "Whoop disconnected" or "couldn't reach Whoop". Never show technical details.

### User Override
Always respect user override without nagging. Acknowledge once, then coach at their selected intensity.

## Meal Tracking

When the user describes a meal or food they ate, estimate the macros and include a "meal" field in your response:
{"description": "chicken and rice", "items": ["200g chicken breast", "Cup of white rice", "Steamed broccoli"], "calories": 650, "protein": 55, "carbs": 60, "fat": 12, "meal_type": "lunch"}

When tracking a meal, also include an "items" array listing individual food items:
{"description": "chicken and rice", "items": ["200g chicken breast", "Cup of white rice", "Steamed broccoli"], "calories": 650, "protein": 55, "carbs": 60, "fat": 12, "meal_type": "lunch"}
Always set meal_type to one of: breakfast, lunch, dinner, snack.

When parsing a meal, also extract journal signals and include in your response:
"journal_signals": {"caffeine": <count>, "alcohol": <bool>}
- Count caffeinated drinks (coffee, espresso, latte, tea, energy drink, pre-workout)
- "decaf" = caffeine 0, "coffee with Mike" = caffeine 1
- Flag alcohol (beer, wine, cocktail, spirits, hard seltzer)
- "virgin mojito" = alcohol false

Be specific about your estimates. If the user just says "I had chicken and rice", ask for approximate portions. Common estimates:
- Chicken breast 200g: 330 cal, 62g protein, 0g carbs, 7g fat
- Cup of white rice: 200 cal, 4g protein, 45g carbs, 0g fat
- Large egg: 70 cal, 6g protein, 0g carbs, 5g fat"""

RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34

_session_lock = asyncio.Lock()

WHOOP_TOOLS = [
    {
        "name": "create_whoop_activity",
        "description": "Log an activity to the user's Whoop. Use for sauna, ice bath, meditation, yoga, stretching, running, cycling, hiking, swimming, walking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "enum": ["sauna", "ice_bath", "meditation", "yoga", "stretching", "running", "cycling", "hiking", "swimming", "walking"]},
                "duration_minutes": {"type": "integer"},
                "start_time": {"type": "string", "description": "ISO 8601 timestamp, optional"},
            },
            "required": ["activity_type", "duration_minutes"],
        },
    },
    {
        "name": "update_whoop_weight",
        "description": "Update body weight on Whoop.",
        "input_schema": {
            "type": "object",
            "properties": {"weight_lbs": {"type": "number"}},
            "required": ["weight_lbs"],
        },
    },
    {
        "name": "set_whoop_alarm",
        "description": "Set or disable Whoop alarm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "time": {"type": "string", "description": "HH:MM format"},
                "enabled": {"type": "boolean"},
            },
            "required": ["time"],
        },
    },
    {
        "name": "delete_whoop_activity",
        "description": "Delete an activity from Whoop. Confirm with user before calling.",
        "input_schema": {
            "type": "object",
            "properties": {"activity_id": {"type": "string"}},
            "required": ["activity_id"],
        },
    },
    {
        "name": "list_whoop_activities",
        "description": "List recent Whoop activities to find an activity ID for deletion or reference.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
        },
    },
    {
        "name": "search_exercise_catalog",
        "description": "Search Whoop exercise catalog by name, equipment, or muscle group.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def assemble_context(program, workout, whoop, history, profile=None, memory=None, active_workout=None, set_history=None, meal_totals=None, db=None, training_log=None):
    parts = []
    if profile:
        profile_parts = [f"User: {profile.get('name', 'unknown')}"]
        if profile.get('experience_level'):
            profile_parts.append(f"Level: {profile['experience_level']}")
        if profile.get('goals'):
            profile_parts.append(f"Goals: {profile['goals']}")
        if profile.get('equipment'):
            profile_parts.append(f"Equipment: {profile['equipment']}")
        if profile.get('training_frequency'):
            profile_parts.append(f"Frequency: {profile['training_frequency']}")
        if profile.get('injuries_notes'):
            profile_parts.append(f"Limitations: {profile['injuries_notes']}")
        if profile.get('calorie_target'):
            profile_parts.append(f"Cal target: {profile['calorie_target']}")
        if profile.get('protein_target'):
            profile_parts.append(f"Protein target: {profile['protein_target']}g")
        parts.append("Profile: " + " | ".join(profile_parts))
    else:
        parts.append("NO USER PROFILE YET — ask intake questions.")

    if memory:
        parts.append(f"\n--- TRAINING MEMORY ---\n{memory}\n--- END TRAINING MEMORY ---")
    else:
        parts.append("\nNo training memory yet. If the user shares a program or plan, store it via memory_update.")

    if training_log:
        parts.append("\n--- TRAINING LOG (recent) ---")
        for entry in training_log[-15:]:  # last 15 entries
            date = entry.get("date", "")
            etype = entry.get("type", "")
            content = entry.get("content", "")
            parts.append(f"  [{date}] {etype}: {content}")
        parts.append("--- END TRAINING LOG ---")

    if active_workout:
        parts.append(f"\n{active_workout}")

    if whoop:
        recovery = whoop.get('recovery_score')
        zone = "GREEN" if recovery and recovery >= RECOVERY_GREEN else "YELLOW" if recovery and recovery >= RECOVERY_YELLOW else "RED"
        strain_str = f" | Strain {whoop['strain']}" if whoop.get('strain') else ""
        sleep_dur = whoop.get('sleep_duration')
        sleep_hrs = f" ({sleep_dur:.1f}h)" if isinstance(sleep_dur, (int, float)) else ""
        sleep_str = f" | Sleep {whoop.get('sleep_score', 'N/A')}%{sleep_hrs}" if whoop.get('sleep_score') else ""
        parts.append(f"Whoop [{zone}]: Recovery {recovery or 'N/A'}% | HRV {whoop.get('hrv', 'N/A')}{sleep_str}{strain_str} | RHR {whoop.get('resting_hr', 'N/A')}")

    # 7-day hrv trend
    if whoop and whoop.get("hrv") and db:
        from sqlalchemy import func as sqlfunc
        from server.models import WhoopData
        hrv_avg = db.query(sqlfunc.avg(WhoopData.hrv)).filter(
            WhoopData.hrv.isnot(None)
        ).scalar()
        if hrv_avg:
            today_hrv = whoop["hrv"]
            hrv_delta = ((today_hrv - hrv_avg) / hrv_avg) * 100
            parts.append(f"HRV trend: today {today_hrv}ms vs 7-day avg {hrv_avg:.0f}ms ({hrv_delta:+.0f}%)")

    # stale data flag
    if whoop and db:
        from server.config import today_eastern
        whoop_date = whoop.get("date")
        if whoop_date and whoop_date != today_eastern():
            parts.append("Note: Whoop data is from yesterday, may not reflect current readiness")

    # tool/catalog availability
    if db:
        from server.models import WhoopToken, ExerciseCatalog
        if db.query(WhoopToken).first():
            parts.append("Whoop tools available: you can log activities, update weight, set alarm")
        if db.query(ExerciseCatalog).first():
            parts.append("Exercise catalog loaded: use search_exercise_catalog to map exercises to Whoop IDs")

    # one-time education messages
    if db:
        from server.models import SystemMemory
        if db.query(WhoopToken).first():
            if not db.query(SystemMemory).filter_by(key="whoop_first_workout_shown").first():
                parts.append(
                    "ONBOARDING: This is the user's first workout with Whoop connected. "
                    "Acknowledge briefly that you can see their recovery data and will "
                    "factor it into training. Keep it short. Don't repeat this."
                )
            if not db.query(SystemMemory).filter_by(key="whoop_journal_education_shown").first():
                parts.append(
                    "ONBOARDING: On the user's first meal log with Whoop connected, briefly mention "
                    "you're tracking caffeine and alcohol to their Whoop journal. Say you won't "
                    "mention it again unless something looks off."
                )

    if set_history:
        parts.append("Recent sets (last 3 workouts):")
        for entry in set_history[:15]:
            rpe_str = f" @ RPE {entry['rpe']}" if entry.get('rpe') else ""
            parts.append(f"  {entry['date']} {entry['exercise']}: {entry['weight']}lbs x {entry['reps']}{rpe_str}")

    if meal_totals:
        parts.append(f"Today's nutrition: {meal_totals['calories']} cal | {meal_totals['protein']}g protein | {meal_totals['carbs']}g carbs | {meal_totals['fat']}g fat")

    if history:
        parts.append("Recent messages:")
        for msg in history[-10:]:
            parts.append(f"  {msg['role']}: {msg['content'][:200]}")

    return "\n".join(parts)


class ClaudeService:

    def __init__(self):
        from server.services.session_manager import SessionManager
        self.session_mgr = SessionManager()

    async def chat(self, message: str, context: str, db=None, date: str | None = None) -> dict:
        from server.config import today_eastern
        today = date or today_eastern()

        # fallback to stateless when no db available (unit tests, intake)
        if db is None:
            return await self._chat_stateless(message, context)

        is_first = self.session_mgr.is_first_message(db, today)

        # daily handoff: summarize old session before creating new
        if self.session_mgr.needs_handoff(db, today):
            await self._do_handoff(db, today)

        session_id = self.session_mgr.get_or_create_session_id(db, today)

        try:
            if is_first:
                # first message: system prompt in --append-system-prompt, context + user msg in -p
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=f"Current context:\n{context}\n\n{message}",
                    is_first=True,
                    system_prompt=SYSTEM_PROMPT,
                )
            else:
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=message,
                    is_first=False,
                )
        except Exception as e:
            logger.error("claude session call failed: %s", e)
            # try recovery: invalidate and retry as fresh session
            self.session_mgr.invalidate_session(db)
            try:
                session_id = self.session_mgr.get_or_create_session_id(db, today)
                raw_text = await _call_claude_session(
                    session_id=session_id,
                    message=f"Current context:\n{context}\n\n{message}",
                    is_first=True,
                    system_prompt=SYSTEM_PROMPT,
                )
            except Exception as e2:
                logger.error("claude recovery failed: %s", e2)
                return self._error_response()

        # parse response
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None, "profile": None, "memory_update": None, "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None}

        # handle tool calls — 2nd call within the same session
        tool_calls = parsed.get("tool_calls", [])
        if tool_calls and db:
            from server.services.whoop_tools import execute_whoop_tool
            results = []
            for tc in tool_calls:
                result = await execute_whoop_tool(tc["name"], tc.get("arguments", {}), db)
                results.append({"tool": tc["name"], "result": result})
            try:
                followup_text = await _call_claude_session(
                    session_id=session_id,
                    message=f"Tool results: {json.dumps(results)}",
                    is_first=False,
                )
                try:
                    parsed = json.loads(followup_text)
                except json.JSONDecodeError:
                    parsed["response"] = followup_text
            except Exception:
                pass

        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None

        return {
            "response": parsed.get("response", raw_text),
            "layout": layout,
            "profile": parsed.get("profile"),
            "memory_update": parsed.get("memory_update"),
            "training_log_entry": parsed.get("training_log_entry"),
            "set_suggestion": parsed.get("set_suggestion"),
            "meal": parsed.get("meal"),
            "workout_plan": parsed.get("workout_plan"),
        }

    async def _chat_stateless(self, message: str, context: str) -> dict:
        """fallback for calls without a db session (unit tests, intake)"""
        system = f"{SYSTEM_PROMPT}\n\nCurrent context:\n{context}"
        try:
            raw_text = await _call_claude_stateless(system, message)
        except Exception as e:
            logger.error("claude call failed: %s", e)
            return self._error_response()
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None, "profile": None, "memory_update": None, "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None}
        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None
        return {
            "response": parsed.get("response", raw_text),
            "layout": layout,
            "profile": parsed.get("profile"),
            "memory_update": parsed.get("memory_update"),
            "training_log_entry": parsed.get("training_log_entry"),
            "set_suggestion": parsed.get("set_suggestion"),
            "meal": parsed.get("meal"),
            "workout_plan": parsed.get("workout_plan"),
        }

    _handoff_lock = asyncio.Lock()

    async def _do_handoff(self, db, today: str):
        """summarize old session and create new one"""
        async with self._handoff_lock:
            if not self.session_mgr.needs_handoff(db, today):
                return
            old_id, old_date = self.session_mgr.get_old_session(db)
            if not old_id:
                return
            try:
                summary_text = await _call_claude_session(
                    session_id=old_id,
                    message="Summarize today's coaching session in 2-3 sentences. Include: what was trained, key performance notes, any program adjustments discussed, and anything to carry forward to tomorrow.",
                    is_first=False,
                )
                try:
                    summary_parsed = json.loads(summary_text)
                    summary_content = summary_parsed.get("response", summary_text)
                except json.JSONDecodeError:
                    summary_content = summary_text
                from server.models import TrainingLog
                db.add(TrainingLog(
                    date=old_date or today,
                    log_type="daily_summary",
                    content=summary_content[:500],
                ))
                db.commit()
            except Exception as e:
                logger.warning("session handoff summary failed: %s", e)
            self.session_mgr.invalidate_session(db)

    def _error_response(self):
        return {"response": "Having trouble reaching Claude right now. Try again in a sec.", "layout": None, "profile": None, "memory_update": None, "training_log_entry": None, "set_suggestion": None, "meal": None, "workout_plan": None}

    async def generate_interview_questions(self, profile_summary: str) -> list[str]:
        """generate personalized interview questions for onboarding."""
        system = (
            "You are SpotMe, an AI strength coach. Generate 3-5 interview questions "
            "to learn what you need to build a personalized training program. "
            "Tailor questions to the athlete's experience level.\n"
            "For beginners: ask about training history, any injuries, what they enjoy, schedule.\n"
            "For intermediate/advanced: ask about current lift numbers (squat, bench, deadlift, OHP), "
            "weak points, PRs they're chasing, injury history, preferred training style.\n"
            "Return ONLY a JSON array of question strings, nothing else."
        )
        raw = await _call_claude_stateless(system, f"Athlete profile: {profile_summary}")
        try:
            # handle both raw array and code-fenced array
            import re
            cleaned = raw.strip()
            fence = re.search(r"```(?:json)?\s*\n?(\[.*?\])\s*\n?```", cleaned, re.DOTALL)
            if fence:
                cleaned = fence.group(1)
            elif not cleaned.startswith("["):
                bracket = re.search(r"\[.*\]", cleaned, re.DOTALL)
                if bracket:
                    cleaned = bracket.group(0)
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and all(isinstance(q, str) for q in parsed):
                return parsed[:5]
        except (json.JSONDecodeError, TypeError):
            pass
        return [
            "What are your current best lifts or recent PRs?",
            "Any injuries or physical limitations I should know about?",
            "What does your typical training week look like right now?",
            "Any specific goals or numbers you're chasing?",
        ]

    async def analyze_form(self, frames_base64: list, context: str) -> dict:
        system = "You are a strength coach analyzing lifting form. Identify issues, suggest corrections, note what looks good."
        message = f"Analyze this lifting form. Context: {context}"
        raw_text = await _call_claude_stateless(system, message)
        return {"analysis": raw_text}


def _extract_json(text: str) -> str:
    import re
    stripped = text.strip()
    # if the whole thing is valid json, return as-is
    if stripped.startswith("{"):
        return stripped
    # extract json from code fences: ```json { ... } ```
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", stripped, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    # find the first { ... } block (greedy, outermost braces)
    brace_match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if brace_match:
        return brace_match.group(0)
    return stripped


async def _call_claude_session(
    session_id: str,
    message: str,
    is_first: bool = False,
    system_prompt: str | None = None,
) -> str:
    """call claude within a persistent daily session."""
    async with _session_lock:
        args = [CLAUDE_BIN, "--print", "--tools", ""]
        if is_first:
            args.extend(["--session-id", session_id, "--model", MODEL])
            if system_prompt:
                args.extend(["--append-system-prompt", system_prompt])
        else:
            args.extend(["--resume", session_id])
        args.extend(["-p", message])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("claude cli timed out after 120s")
        if proc.returncode != 0:
            error = stderr.decode().strip()
            logger.error("claude session error: %s", error)
            raise RuntimeError(f"claude cli failed: {error}")
        raw = stdout.decode().strip()
        return _extract_json(raw)


async def _call_claude_stateless(system_prompt: str, message: str) -> str:
    """call claude without session persistence (for one-off calls)."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--no-session-persistence",
        "--model", MODEL,
        "--tools", "",
        "--append-system-prompt", system_prompt,
        "-p", message,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("claude cli timed out after 120s")
    if proc.returncode != 0:
        error = stderr.decode().strip()
        logger.error("claude cli error: %s", error)
        raise RuntimeError(f"claude cli failed: {error}")
    raw = stdout.decode().strip()
    return _extract_json(raw)
