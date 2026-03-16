from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Workout, Exercise, Set, WhoopData
from server.schemas import WorkoutCompleteRequest, WorkoutCompleteResponse, SetLog
from server.config import settings

router = APIRouter()

@router.get("/workout/today")
async def get_today_workout(db: Session = Depends(get_db)):
    from datetime import date
    today = date.today().isoformat()
    workout = db.query(Workout).filter_by(date=today, status="active").first()
    if not workout:
        return {"status": "no_workout", "exercises": []}
    exercises = db.query(Exercise).filter_by(workout_id=workout.id).order_by(Exercise.order).all()
    exercise_data = []
    for ex in exercises:
        sets = db.query(Set).filter_by(exercise_id=ex.id).all()
        exercise_data.append({"id": ex.id, "name": ex.name, "order": ex.order, "sets": [{"id": s.id, "weight": s.weight, "reps": s.reps, "rpe": s.rpe, "completed": s.completed} for s in sets]})
    whoop = db.query(WhoopData).order_by(WhoopData.date.desc()).first()
    return {"id": workout.id, "date": workout.date, "status": workout.status, "exercises": exercise_data, "whoop_recovery": whoop.recovery_score if whoop else None}

@router.post("/workout/set")
async def log_set(set_log: SetLog, db: Session = Depends(get_db)):
    from datetime import date
    today = date.today().isoformat()
    workout = db.query(Workout).filter_by(date=today, status="active").first()
    if not workout:
        return {"error": "no active workout"}
    exercise = db.query(Exercise).filter_by(workout_id=workout.id, name=set_log.exercise_name).first()
    if not exercise:
        return {"error": f"exercise '{set_log.exercise_name}' not found"}
    new_set = Set(exercise_id=exercise.id, weight=set_log.weight, reps=set_log.reps, rpe=set_log.rpe, completed=True, notes=set_log.notes)
    db.add(new_set)
    db.commit()
    return {"id": new_set.id, "logged": True}

@router.post("/workout/complete", response_model=WorkoutCompleteResponse)
async def complete_workout(request: WorkoutCompleteRequest, db: Session = Depends(get_db)):
    workout = db.query(Workout).filter_by(id=request.workout_id).first()
    if not workout:
        return WorkoutCompleteResponse(status="not_found", whoop_synced=False)
    workout.status = "completed"
    db.commit()
    whoop_synced = False
    whoop_error = None
    if settings.whoop_access_token:
        try:
            from whoop import WhoopClient
            from server.services.whoop_service import push_workout_to_whoop
            client = WhoopClient(token=settings.whoop_access_token)
            result = await push_workout_to_whoop(db, client, workout.id)
            whoop_synced = result.get("synced", False)
            if not whoop_synced:
                whoop_error = result.get("error", "unknown error")
        except Exception as e:
            whoop_error = str(e)
    else:
        whoop_error = "whoop not configured"
    return WorkoutCompleteResponse(status="completed", whoop_synced=whoop_synced, whoop_error=whoop_error)
