import logging
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import SystemMemory, Workout
from server.services.program_parser import parse_program

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/program")
async def get_program(db: Session = Depends(get_db)):
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"has_program": False, "weeks": [], "progression": []}

    result = parse_program(memory.content)

    total = db.query(Workout).count()
    completed = db.query(Workout).filter_by(status="completed").count()

    return {
        "has_program": True,
        "weeks": result["weeks"],
        "progression": result["progression"],
        "stats": {
            "total_workouts": total,
            "completed_workouts": completed,
            "today": date.today().isoformat(),
        },
    }
