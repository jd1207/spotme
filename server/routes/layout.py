from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.services.claude_service import ClaudeService, assemble_context
from server.models import Program, WhoopData
from server.config import settings

router = APIRouter()

@router.get("/layout")
async def get_layout(screen: str = "dashboard", db: Session = Depends(get_db)):
    program = db.query(Program).order_by(Program.updated_at.desc()).first()
    program_dict = {"name": program.name, "goal": program.goal, "phase": program.phase} if program else None
    whoop = db.query(WhoopData).order_by(WhoopData.date.desc()).first()
    whoop_dict = {"recovery_score": whoop.recovery_score, "hrv": whoop.hrv, "sleep_score": whoop.sleep_score} if whoop else None
    context = assemble_context(program_dict, None, whoop_dict, [])
    try:
        service = ClaudeService()
        result = await service.chat(f"Generate a {screen} layout for the user. Return layout JSON only.", context)
        if result["layout"]:
            return result["layout"]
    except Exception:
        pass
    return {"screen": screen, "layout": [{"type": "header", "title": "SpotMe", "subtitle": "Welcome back"}, {"type": "action_button", "label": "Start Workout", "action": "start_workout"}]}
