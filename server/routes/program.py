import logging
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import SystemMemory, Workout

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/program")
async def get_program(db: Session = Depends(get_db)):
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"has_program": False, "content": None, "stats": None}

    total = db.query(Workout).count()
    completed = db.query(Workout).filter_by(status="completed").count()
    today = date.today().isoformat()

    return {
        "has_program": True,
        "content": memory.content,
        "stats": {
            "total_workouts": total,
            "completed_workouts": completed,
            "today": today,
        },
    }
