from __future__ import annotations
import json
import anthropic
from server.services.layout_service import validate_layout

SYSTEM_PROMPT = """You are SpotMe, an AI strength coach. You help the user with their workout program, provide form feedback, and adjust training based on their Whoop biometric data.

When responding, return JSON with two fields:
- "response": your coaching text (string)
- "layout": optional UI layout descriptor (object or null)

Layout components available: header, stat_card, exercise_card, set_logger, rest_timer, text_block, video_prompt, chart, action_button, chat_bubble.

Always respond with valid JSON only."""

def assemble_context(program, workout, whoop, history):
    parts = []
    if program:
        parts.append(f"Program: {program['name']} | Goal: {program['goal']} | Phase: {program['phase']}")
    else:
        parts.append("No active program.")
    if workout:
        exercises = workout.get("exercises", [])
        ex_str = ", ".join(f"{e['name']} {e.get('sets','')}x{e.get('reps','')}@{e.get('weight','')}" for e in exercises)
        parts.append(f"Today's workout: {ex_str}")
    else:
        parts.append("No workout scheduled today.")
    if whoop:
        parts.append(f"Whoop: Recovery {whoop.get('recovery_score', 'N/A')}% | HRV {whoop.get('hrv', 'N/A')} | Sleep {whoop.get('sleep_score', 'N/A')}%")
    else:
        parts.append("Whoop data unavailable.")
    if history:
        parts.append("Recent conversation:")
        for msg in history[-5:]:
            parts.append(f"  {msg['role']}: {msg['content']}")
    return "\n".join(parts)

class ClaudeService:
    def __init__(self, api_key):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(self, message, context):
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=f"{SYSTEM_PROMPT}\n\nCurrent context:\n{context}",
            messages=[{"role": "user", "content": message}],
        )
        raw_text = response.content[0].text
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return {"response": raw_text, "layout": None}
        layout = parsed.get("layout")
        if layout:
            validation = validate_layout(layout)
            layout = validation["layout"] if validation["valid"] else None
        return {"response": parsed.get("response", raw_text), "layout": layout}

    async def analyze_form(self, frames_base64, context):
        content = [{"type": "text", "text": f"Analyze this lifting form. Context: {context}"}]
        for frame in frames_base64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame}})
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are a strength coach analyzing lifting form from video frames. Identify issues with technique, suggest corrections, and note what looks good.",
            messages=[{"role": "user", "content": content}],
        )
        return {"analysis": response.content[0].text}
