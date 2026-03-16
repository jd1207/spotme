from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Workout, Exercise, Set, WhoopData

router = APIRouter()

@router.get("/progress")
async def get_progress(db: Session = Depends(get_db)):
    bench_sets = db.query(Set).join(Exercise).join(Workout).filter(Exercise.name.ilike("%bench press%")).filter(Set.completed == True).order_by(Workout.date).all()
    bench_trend = [{"weight": s.weight, "reps": s.reps} for s in bench_sets]
    whoop_data = db.query(WhoopData).order_by(WhoopData.date.desc()).limit(30).all()
    whoop_trends = {
        "recovery": [{"date": w.date, "value": w.recovery_score} for w in reversed(whoop_data)],
        "hrv": [{"date": w.date, "value": w.hrv} for w in reversed(whoop_data)],
    }
    return {"bench_1rm_trend": bench_trend, "volume_trend": [], "whoop_trends": whoop_trends}
