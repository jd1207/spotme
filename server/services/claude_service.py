from __future__ import annotations
import json
import logging
import anthropic
from server.services.layout_service import validate_layout

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are SpotMe, an AI strength coach running inside a workout tracking app. You help the user train, log sets, adjust programming, and provide coaching based on their data.

You have access to persistent TRAINING MEMORY (shown in context). This is your long-term knowledge about the athlete — their program, history, projections, and preferences. It persists across all conversations.

## Rules

1. If the user shares a training plan, program, or detailed athlete info, STORE IT by including a "memory_update" field in your response. This replaces the current training memory entirely, so include everything important — don't just add new info, merge it with what you already know.

2. If the user logs a set or completes a workout, update memory to reflect progress (mark sessions done, note performance, adjust projections if needed).

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
  "memory_update": "full updated training memory as markdown"
}
```
- "response" is required
- "layout" is optional (UI layout descriptor, usually null)
- "set_suggestion" is optional — ONLY include when the user is actively in a workout (workout context shows an active workout). Do NOT suggest specific sets during casual pre-workout chat:
  {"exercise": "Bench Press", "weight": 225, "reps": 5, "basis": "based on last session + green recovery"}
- "profile" is optional (only when you learn new profile info). Supported fields: name, goals, experience_level, equipment, training_frequency, injuries_notes, calorie_target (int), protein_target (int). When the user mentions daily nutrition targets, set calorie_target and protein_target.
- "memory_update" is optional (only when training memory should change)
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

## Meal Tracking

When the user describes a meal or food they ate, estimate the macros and include a "meal" field in your response:
{"description": "chicken and rice", "items": ["200g chicken breast", "Cup of white rice", "Steamed broccoli"], "calories": 650, "protein": 55, "carbs": 60, "fat": 12, "meal_type": "lunch"}

When tracking a meal, also include an "items" array listing individual food items:
{"description": "chicken and rice", "items": ["200g chicken breast", "Cup of white rice", "Steamed broccoli"], "calories": 650, "protein": 55, "carbs": 60, "fat": 12, "meal_type": "lunch"}
Always set meal_type to one of: breakfast, lunch, dinner, snack.

Be specific about your estimates. If the user just says "I had chicken and rice", ask for approximate portions. Common estimates:
- Chicken breast 200g: 330 cal, 62g protein, 0g carbs, 7g fat
- Cup of white rice: 200 cal, 4g protein, 45g carbs, 0g fat
- Large egg: 70 cal, 6g protein, 0g carbs, 5g fat"""

RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34

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


def assemble_context(program, workout, whoop, history, profile=None, memory=None, active_workout=None, set_history=None, meal_totals=None):
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

    async def chat(self, message: str, context: str, db=None) -> dict:
        system = f"{SYSTEM_PROMPT}\n\nCurrent context:\n{context}"
        try:
            from server.models import WhoopToken
            whoop_connected = db.query(WhoopToken).first() is not None if db else False

            if whoop_connected:
                from server.services.whoop_tools import execute_whoop_tool
                raw_text = await _call_claude_with_tools(
                    system_prompt=system,
                    message=message,
                    tools=WHOOP_TOOLS,
                    tool_executor=execute_whoop_tool,
                    db=db,
                )
            else:
                raw_text = await _call_claude(system, message)
        except Exception as e:
            logger.error("claude call failed: %s", e)
            return {"response": "Having trouble reaching Claude right now. Try again in a sec.", "layout": None, "profile": None, "memory_update": None, "set_suggestion": None, "meal": None, "workout_plan": None}
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None, "profile": None, "memory_update": None, "set_suggestion": None, "meal": None, "workout_plan": None}
        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None
        return {
            "response": parsed.get("response", raw_text),
            "layout": layout,
            "profile": parsed.get("profile"),
            "memory_update": parsed.get("memory_update"),
            "set_suggestion": parsed.get("set_suggestion"),
            "meal": parsed.get("meal"),
            "workout_plan": parsed.get("workout_plan"),
        }

    async def analyze_form(self, frames_base64: list, context: str) -> dict:
        system = "You are a strength coach analyzing lifting form. Identify issues, suggest corrections, note what looks good."
        message = f"Analyze this lifting form. Context: {context}"
        raw_text = await _call_claude(system, message)
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


async def _call_claude(system_prompt: str, message: str) -> str:
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    )
    raw = response.content[0].text
    return _extract_json(raw.strip())


MAX_TOOL_ITERATIONS = 3


async def _call_claude_with_tools(
    system_prompt: str,
    message: str,
    tools: list[dict],
    tool_executor,
    db,
    history: list[dict] | None = None,
) -> str:
    """call claude with tool-use loop, executing tools until final text response."""
    client = anthropic.AsyncAnthropic()
    messages = list(history) if history else []
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

        if response.stop_reason != "tool_use":
            # final text response
            text_blocks = [b.text for b in response.content if b.type == "text"]
            raw = " ".join(text_blocks)
            return _extract_json(raw.strip())

        # execute each tool call
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await tool_executor(block.name, block.input, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        messages.append({"role": "user", "content": tool_results})

    # max iterations reached
    return '{"response": "I had trouble completing that action.", "layout": null}'
