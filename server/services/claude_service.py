from __future__ import annotations
import asyncio
import json
import logging
import shutil
from server.services.layout_service import validate_layout

logger = logging.getLogger(__name__)

CLAUDE_BIN = shutil.which("claude") or "/home/deck/.local/bin/claude"

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
  "profile": {"name": "...", ...},
  "memory_update": "full updated training memory as markdown"
}
```
- "response" is required
- "layout" is optional (UI layout descriptor, usually null)
- "profile" is optional (only when you learn new profile info)
- "memory_update" is optional (only when training memory should change)

Layout components available: header, stat_card, exercise_card, set_logger, rest_timer, text_block, video_prompt, chart, action_button, chat_bubble."""


def assemble_context(program, workout, whoop, history, profile=None, memory=None, active_workout=None):
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
        parts.append(f"Whoop: Recovery {whoop.get('recovery_score', 'N/A')}% | HRV {whoop.get('hrv', 'N/A')} | Sleep {whoop.get('sleep_score', 'N/A')}%")

    if history:
        parts.append("Recent messages:")
        for msg in history[-5:]:
            parts.append(f"  {msg['role']}: {msg['content'][:200]}")

    return "\n".join(parts)


class ClaudeService:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    async def chat(self, message: str, context: str) -> dict:
        system = f"{SYSTEM_PROMPT}\n\nCurrent context:\n{context}"
        try:
            raw_text = await _call_claude(system, message)
        except RuntimeError as e:
            logger.error("claude call failed: %s", e)
            return {"response": "Having trouble reaching Claude right now. Try again in a sec.", "layout": None, "profile": None, "memory_update": None}
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None, "profile": None, "memory_update": None}
        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None
        return {
            "response": parsed.get("response", raw_text),
            "layout": layout,
            "profile": parsed.get("profile"),
            "memory_update": parsed.get("memory_update"),
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


async def _call_claude(system: str, message: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--append-system-prompt", system,
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
