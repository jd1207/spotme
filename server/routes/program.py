import logging
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import SystemMemory, Workout, Exercise, Set
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


@router.get("/program/week/{week_number}")
async def get_program_week(week_number: int, db: Session = Depends(get_db)):
    """return detailed set data for all days in a program week"""
    memory = db.query(SystemMemory).filter_by(key="training_plan").first()
    if not memory or not memory.content:
        return {"week": week_number, "days": []}

    result = parse_program(memory.content)
    weeks = result.get("weeks", [])

    week = next((w for w in weeks if w["number"] == week_number), None)
    if not week:
        return {"week": week_number, "days": []}

    completed_workouts = db.query(Workout).filter_by(status="completed").all()

    enriched_days = []
    for day in week.get("days", []):
        day_data = {**day, "exercises": [], "source": "planned", "summary": None}

        if day["status"] != "completed":
            enriched_days.append(day_data)
            continue

        # find the best-matching completed workout by type keyword
        day_first_word = day["type"].lower().split()[0]
        matched_workout = None
        for w in completed_workouts:
            if day_first_word in (w.type or "").lower():
                matched_workout = w

        if not matched_workout:
            enriched_days.append(day_data)
            continue

        day_data["source"] = "logged"
        exercises = (
            db.query(Exercise)
            .filter_by(workout_id=matched_workout.id)
            .order_by(Exercise.order)
            .all()
        )
        for ex in exercises:
            sets = (
                db.query(Set)
                .filter_by(exercise_id=ex.id)
                .order_by(Set.order)
                .all()
            )
            day_data["exercises"].append({
                "name": ex.name,
                "sets": [
                    {
                        "weight": s.weight,
                        "reps": s.reps,
                        "rpe": s.rpe,
                        "set_type": s.set_type or "working",
                        "status": s.status or ("completed" if s.completed else "pending"),
                        "target_weight": s.target_weight,
                        "target_reps": s.target_reps,
                    }
                    for s in sets
                ],
            })

        day_data["summary"] = _build_summary(day_data["exercises"])
        enriched_days.append(day_data)

    return {"week": week_number, "days": enriched_days}


def _build_summary(exercises: list) -> dict:
    """compute total_sets, top_set, and avg_rpe from exercise list"""
    total_sets = sum(len(e["sets"]) for e in exercises)
    top_weight = 0
    top_set = ""
    rpe_vals = []

    for ex in exercises:
        for s in ex["sets"]:
            if s["set_type"] != "working":
                continue
            if s["weight"] > top_weight:
                top_weight = s["weight"]
                top_set = f"{s['weight']}x{s['reps']}"
            if s["rpe"] is not None:
                rpe_vals.append(s["rpe"])

    avg_rpe = round(sum(rpe_vals) / len(rpe_vals), 1) if rpe_vals else None
    return {"total_sets": total_sets, "top_set": top_set, "avg_rpe": avg_rpe}
