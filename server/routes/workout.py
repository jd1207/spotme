from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Workout, Exercise, Set, WhoopData
from server.schemas import WorkoutCompleteRequest, WorkoutCompleteResponse, SetLog, CompleteSetRequest
from server.services.workout_sequencer import complete_set as sequencer_complete_set
from server.config import today_eastern, TIMEZONE

router = APIRouter()


@router.post("/workout/start")
async def start_workout(data: dict, db: Session = Depends(get_db)):
    today = today_eastern()
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
    from server.models import SystemMemory
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"summary": "No program loaded. Tell Claude about your training plan in Chat."}

    now = datetime.now(TIMEZONE)
    day_name = now.strftime("%A")
    day_abbrev = now.strftime("%a")

    lines = memory.content.split("\n")
    for line in lines:
        lower = line.lower().strip()
        if not lower or lower.startswith("#"):
            continue
        if day_name.lower() in lower or day_abbrev.lower() in lower:
            clean = line.strip().strip("-*|").strip()
            if len(clean) > 10:
                return {"summary": clean}

    # fallback: match "Day N" based on weekday number (Mon=1, Tue=2, etc.)
    weekday_num = now.weekday()  # 0=Mon
    for line in lines:
        lower = line.lower().strip()
        if f"day {weekday_num + 1}" in lower and len(line.strip()) > 10:
            return {"summary": line.strip().strip("-*|").strip()}

    return {"summary": f"No {day_name} workout found in plan. Chat with Claude to update your program."}


@router.get("/workout/recent")
async def get_recent_workouts(db: Session = Depends(get_db)):
    workouts = db.query(Workout).order_by(Workout.date.desc()).limit(20).all()
    result = []
    for w in workouts:
        exercises = db.query(Exercise).filter_by(workout_id=w.id).order_by(Exercise.order).all()
        whoop = db.query(WhoopData).filter_by(date=w.date).first()
        exercise_list = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            if sets:
                exercise_list.append({
                    "name": ex.name,
                    "sets": [{"weight": s.weight, "reps": s.reps, "rpe": s.rpe} for s in sets],
                })
        result.append({
            "id": w.id, "date": w.date, "type": w.type,
            "status": w.status, "duration": w.duration,
            "exercises": exercise_list,
            "recovery": whoop.recovery_score if whoop else None,
        })
    return result


@router.get("/workout/today")
async def get_today_workout(db: Session = Depends(get_db)):
    today = today_eastern()
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
    today = today_eastern()
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


@router.post("/workout/complete-set")
async def complete_set_endpoint(request: CompleteSetRequest, db: Session = Depends(get_db)):
    result = sequencer_complete_set(
        db, request.set_id, request.actual_weight, request.actual_reps,
        request.actual_rpe, request.feel
    )
    return result


@router.get("/exercise/last/{name}")
async def get_last_exercise(name: str, db: Session = Depends(get_db)):
    """get the most recent completed sets for an exercise"""
    sets = (
        db.query(Set.weight, Set.reps, Set.rpe, Workout.date)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .join(Workout, Exercise.workout_id == Workout.id)
        .filter(Exercise.name == name, Set.completed == True)
        .order_by(Workout.date.desc())
        .limit(5)
        .all()
    )
    return {
        "sets": [
            {"weight": s.weight, "reps": s.reps, "rpe": s.rpe, "date": s.date}
            for s in sets
        ]
    }


@router.post("/workout/complete", response_model=WorkoutCompleteResponse)
async def complete_workout(request: WorkoutCompleteRequest, db: Session = Depends(get_db)):
    workout = db.query(Workout).filter_by(id=request.workout_id).first()
    if not workout:
        return WorkoutCompleteResponse(status="not_found", whoop_synced=False)
    workout.status = "completed"
    db.commit()

    whoop_synced = False
    whoop_error = None
    from server.models import WhoopToken
    token = db.query(WhoopToken).first()
    if token:
        try:
            from server.services.whoop_service import push_workout_to_whoop
            result = await push_workout_to_whoop(db, workout.id)
            whoop_synced = result.get("synced", False)
            if not whoop_synced:
                whoop_error = result.get("error", "unknown error")
        except ImportError:
            whoop_error = "whoop-write-api not installed"
        except Exception as e:
            whoop_error = str(e)
    else:
        whoop_error = "whoop not configured"
    return WorkoutCompleteResponse(status="completed", whoop_synced=whoop_synced, whoop_error=whoop_error)
