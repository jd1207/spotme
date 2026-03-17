from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Workout, Exercise, Set, WhoopData
from server.schemas import WorkoutCompleteRequest, WorkoutCompleteResponse, SetLog
from server.config import settings

router = APIRouter()


@router.post("/workout/start")
async def start_workout(data: dict, db: Session = Depends(get_db)):
    from datetime import date
    today = date.today().isoformat()
    # atomic check-and-create to prevent race conditions
    existing = db.query(Workout).filter_by(date=today, status="active").first()
    if existing:
        return {"id": existing.id, "date": existing.date, "status": "active", "resumed": True}
    workout = Workout(
        date=today,
        type=data.get("type", "strength"),
        status="active",
        notes=data.get("notes"),
    )
    db.add(workout)
    try:
        db.commit()
    except Exception:
        db.rollback()
        existing = db.query(Workout).filter_by(date=today, status="active").first()
        if existing:
            return {"id": existing.id, "date": existing.date, "status": "active", "resumed": True}
        raise
    return {"id": workout.id, "date": workout.date, "status": "active", "resumed": False}


@router.get("/workout/next")
async def get_next_workout(db: Session = Depends(get_db)):
    from datetime import date
    from server.models import SystemMemory
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"summary": "No program loaded yet. Chat with Claude to set one up."}
    # figure out what day it is and match to schedule
    today = date.today()
    day_name = today.strftime("%A")
    # scan memory for today's day name or next scheduled session
    lines = memory.content.split("\n")
    for line in lines:
        if day_name.lower() in line.lower() and any(w in line.lower() for w in ["bench", "leg", "pull", "push", "upper", "lower", "back", "arms", "shoulder", "squat", "deadlift", "press"]):
            # clean up the line
            summary = line.strip().strip("|").strip("- ").strip()
            if len(summary) > 10:
                return {"summary": f"{day_name}: {summary}"}
    # fallback: return the first few schedule-related lines
    schedule_lines = [l.strip() for l in lines if any(w in l.lower() for w in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "week"]) and len(l.strip()) > 5]
    if schedule_lines:
        return {"summary": schedule_lines[0]}
    return {"summary": "Check your program in Chat with Claude."}


@router.get("/workout/recent")
async def get_recent_workouts(db: Session = Depends(get_db)):
    workouts = db.query(Workout).order_by(Workout.date.desc()).limit(20).all()
    return [{"id": w.id, "date": w.date, "type": w.type, "status": w.status, "duration": w.duration} for w in workouts]


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
    whoop = db.query(WhoopData).filter_by(date=today).first()
    return {"id": workout.id, "date": workout.date, "status": workout.status, "exercises": exercise_data, "whoop_recovery": whoop.recovery_score if whoop else None}


@router.post("/workout/set")
async def log_set(set_log: SetLog, db: Session = Depends(get_db)):
    from datetime import date
    today = date.today().isoformat()
    workout = db.query(Workout).filter_by(date=today, status="active").first()
    if not workout:
        raise HTTPException(status_code=404, detail="no active workout")
    exercise = db.query(Exercise).filter_by(workout_id=workout.id, name=set_log.exercise_name).first()
    if not exercise:
        raise HTTPException(status_code=404, detail=f"exercise '{set_log.exercise_name}' not found")
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
            from server.services.whoop_service import (
                create_whoop_client,
                push_workout_to_whoop,
            )
            client = create_whoop_client()
            result = await push_workout_to_whoop(db, client, workout.id)
            whoop_synced = result.get("synced", False)
            if not whoop_synced:
                whoop_error = result.get("error", "unknown error")
        except ImportError:
            whoop_error = "whoop-write-api not installed"
    else:
        whoop_error = "whoop not configured"
    return WorkoutCompleteResponse(status="completed", whoop_synced=whoop_synced, whoop_error=whoop_error)
