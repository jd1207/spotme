from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.schemas import ChatRequest, ChatResponse
from server.services.claude_service import ClaudeService, assemble_context
from server.models import Program, Workout, WhoopData, Conversation
from server.config import settings

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    program = db.query(Program).order_by(Program.updated_at.desc()).first()
    program_dict = {"name": program.name, "goal": program.goal, "phase": program.phase} if program else None
    whoop = db.query(WhoopData).order_by(WhoopData.date.desc()).first()
    whoop_dict = {"recovery_score": whoop.recovery_score, "hrv": whoop.hrv, "sleep_score": whoop.sleep_score} if whoop else None
    history = db.query(Conversation).order_by(Conversation.created_at.desc()).limit(5).all()
    history_dicts = [{"role": h.role, "content": h.content} for h in reversed(history)]
    context = assemble_context(program_dict, None, whoop_dict, history_dicts)
    service = ClaudeService(api_key=settings.anthropic_api_key)
    result = await service.chat(request.message, context)
    db.add(Conversation(role="user", content=request.message, context_type="chat"))
    db.add(Conversation(role="assistant", content=result["response"], context_type="chat"))
    db.commit()
    return ChatResponse(response=result["response"], layout=result["layout"])
