import asyncio
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from server.database import get_db
from server.services.claude_service import (
    CLAUDE_BIN, MODEL, SYSTEM_PROMPT, _session_lock, assemble_context,
)
from server.services.session_manager import SessionManager
from server.models import (
    SystemMemory, Conversation, UserProfile, WhoopData, Meal, TrainingLog,
)
from server.config import today_eastern
from server.schemas import ChatRequest
from sqlalchemy import func as sqlfunc

logger = logging.getLogger(__name__)
router = APIRouter()
session_mgr = SessionManager()


def _build_context(db: Session):
    """build claude context from db state (shared logic with chat route)"""
    profile = db.query(UserProfile).first()
    profile_dict = None
    if profile:
        profile_dict = {
            "name": profile.name, "goals": profile.goals,
            "experience_level": profile.experience_level,
            "equipment": profile.equipment,
            "training_frequency": profile.training_frequency,
            "injuries_notes": profile.injuries_notes,
            "calorie_target": profile.calorie_target,
            "protein_target": profile.protein_target,
        }

    whoop_dict = None
    whoop = db.query(WhoopData).filter_by(date=today_eastern()).first()
    if whoop:
        whoop_dict = {
            "recovery_score": whoop.recovery_score, "hrv": whoop.hrv,
            "resting_hr": whoop.resting_hr, "sleep_score": whoop.sleep_score,
            "sleep_duration": whoop.sleep_duration, "strain": whoop.strain,
        }

    memory_row = db.query(SystemMemory).filter_by(key="training_plan").first()
    memory_text = memory_row.content if memory_row else None

    recent_logs = (
        db.query(TrainingLog).order_by(TrainingLog.id.desc()).limit(15).all()
    )
    training_log_dicts = [
        {"date": log.date, "type": log.log_type, "content": log.content}
        for log in reversed(recent_logs)
    ]

    # today's meal totals
    meal_row = db.query(
        sqlfunc.sum(Meal.calories).label("calories"),
        sqlfunc.sum(Meal.protein).label("protein"),
        sqlfunc.sum(Meal.carbs).label("carbs"),
        sqlfunc.sum(Meal.fat).label("fat"),
    ).filter(Meal.date == today_eastern()).first()
    meal_totals = None
    if meal_row and meal_row.calories:
        meal_totals = {
            "calories": meal_row.calories,
            "protein": round(meal_row.protein or 0, 1),
            "carbs": round(meal_row.carbs or 0, 1),
            "fat": round(meal_row.fat or 0, 1),
        }

    return assemble_context(
        None, None, whoop_dict, [], profile_dict, memory_text,
        training_log=training_log_dicts, db=db, meal_totals=meal_totals,
    )


@router.post("/chat/stream")
async def stream_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """sse endpoint that streams claude's response token by token"""
    message = request.message
    request_date = request.date or today_eastern()

    context = _build_context(db)

    is_first = session_mgr.is_first_message(db, request_date)
    if session_mgr.needs_handoff(db, request_date):
        from server.services.claude_service import ClaudeService
        svc = ClaudeService()
        await svc._do_handoff(db, request_date)

    session_id = session_mgr.get_or_create_session_id(db, request_date)

    args = [
        CLAUDE_BIN, "--print", "--output-format", "stream-json",
        "--verbose", "--tools", "",
    ]
    if is_first:
        args.extend([
            "--session-id", session_id,
            "--model", MODEL,
            "--append-system-prompt", SYSTEM_PROMPT,
        ])
        msg = f"Current context:\n{context}\n\n{message}"
    else:
        args.extend(["--resume", session_id])
        msg = message
    args.extend(["-p", msg])

    async def event_stream():
        # acquire lock only to start the process, then release
        async with _session_lock:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        # stream outside the lock
        full_text = ""
        try:
            async for line in proc.stdout:
                decoded = line.decode().strip()
                if not decoded:
                    continue
                try:
                    event = json.loads(decoded)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "assistant":
                    content = event.get("message", {}).get("content", [])
                    for block in content:
                        if block.get("type") == "text":
                            text = block["text"]
                            full_text += text
                            yield f"data: {json.dumps({'text': text})}\n\n"
            await proc.wait()
        except Exception as e:
            logger.error("stream error: %s", e)
            proc.kill()
            await proc.wait()

        # save conversation
        db.add(Conversation(
            role="user", content=message,
            context_type="chat", date=request_date,
        ))
        db.add(Conversation(
            role="assistant", content=full_text,
            context_type="chat", date=request_date,
        ))
        db.commit()

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
    )
