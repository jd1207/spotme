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


@router.get("/progress/prs")
async def get_prs(db: Session = Depends(get_db)):
    """estimated 1RM PRs per exercise using Epley formula"""
    exercise_names = [row[0] for row in db.query(Exercise.name).distinct().all()]
    prs = []
    for name in exercise_names:
        best = (
            db.query(Set.weight, Set.reps, Workout.date)
            .join(Exercise, Set.exercise_id == Exercise.id)
            .join(Workout, Exercise.workout_id == Workout.id)
            .filter(Exercise.name == name, Set.completed == True, Set.reps <= 10, Set.reps >= 1)
            .all()
        )
        if not best:
            continue
        top = max(best, key=lambda s: s.weight * (1 + s.reps / 30.0))
        e1rm = round(top.weight * (1 + top.reps / 30.0), 1)
        prs.append({"exercise": name, "weight": top.weight, "reps": top.reps, "e1rm": e1rm, "date": top.date})
    prs.sort(key=lambda x: x["e1rm"], reverse=True)
    return {"prs": prs}
