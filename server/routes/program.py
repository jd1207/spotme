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
    # count workouts with at least one exercise logged (not just status=completed)
    completed = (
        db.query(Workout)
        .filter(Workout.id.in_(
            db.query(Exercise.workout_id).distinct()
        ))
        .count()
    )

    return {
        "has_program": True,
        "weeks": [
            {**w, "start_date": w.get("start_date")}
            for w in result["weeks"]
        ],
        "progression": result["progression"],
        "stats": {
            "total_workouts": total,
            "completed_workouts": completed,
            "today": date.today().isoformat(),
        },
    }


_DAY_KEYWORDS = {
    "pull": ["pull-up", "pullup", "row", "lat", "curl", "shrug", "face pull"],
    "back": ["pull-up", "pullup", "row", "lat", "curl", "shrug", "face pull"],
    "bench": ["bench press", "db flat press", "cable fly", "flye", "tricep"],
    "heavy": ["bench press", "db flat press", "cable fly", "flye", "tricep"],
    "volume": ["bench press", "db flat press", "cable fly", "flye", "tricep"],
    "legs": ["deadlift", "squat", "leg press", "leg curl", "calf", "rdl", "lunge"],
    "arms": ["curl", "tricep", "extension", "pushdown"],
    "shoulders": ["lateral raise", "ohp", "shoulder press"],
}


def _score_workout_match(exercise_names: list[str], day_type: str) -> int:
    """score how well a workout's exercises match a program day type"""
    text = ' '.join(e.lower() for e in exercise_names)
    best_score = 0
    for word in day_type.lower().split():
        keywords = _DAY_KEYWORDS.get(word, [])
        score = sum(1 for kw in keywords if kw in text)
        best_score = max(best_score, score)
    return best_score


# day-of-week offsets from the sunday start_date
# pull/back (fri) opens the new cycle (-2), legs (sat) CLOSES the cycle (+6)
_DAY_OFFSETS = {
    "Fri": -2, "Sat": 6, "Sun": 0, "Mon": 1,
    "Tue": 2, "Tue/Wed": 2, "Wed": 3, "Thu": 4,
}


def _expected_date(start_date: str, day_abbrev: str) -> str | None:
    """calculate the expected calendar date for a program day"""
    from datetime import datetime, timedelta
    offset = _DAY_OFFSETS.get(day_abbrev)
    if offset is None:
        return None
    dt = datetime.fromisoformat(start_date) + timedelta(days=offset)
    return dt.date().isoformat()


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

    # fetch all workouts in a broad range around this week
    start_date = week.get("start_date")
    if start_date:
        from datetime import datetime, timedelta
        start_dt = datetime.fromisoformat(start_date)
        range_start = (start_dt - timedelta(days=3)).date().isoformat()
        range_end = (start_dt + timedelta(days=8)).date().isoformat()
        all_workouts = (
            db.query(Workout)
            .filter(Workout.date >= range_start, Workout.date < range_end)
            .all()
        )
    else:
        all_workouts = db.query(Workout).all()

    # preload exercise names per workout
    workout_exercises: dict[int, list[str]] = {}
    for w in all_workouts:
        exercises = db.query(Exercise).filter_by(workout_id=w.id).all()
        workout_exercises[w.id] = [e.name for e in exercises]

    # only consider workouts with logged exercises
    all_workouts = [w for w in all_workouts if workout_exercises.get(w.id)]

    used_workout_ids: set[int] = set()

    enriched_days = []
    for day in week.get("days", []):
        day_data = {**day, "exercises": [], "source": "planned", "summary": None}

        # find the best workout: must match by exercise type AND be near the expected date
        expected = _expected_date(start_date, day["day_of_week"]) if start_date else None
        best_match = None
        best_score = 0
        for w in all_workouts:
            if w.id in used_workout_ids:
                continue
            # skip workouts too far from expected date (±1 day tolerance)
            if expected and w.date:
                from datetime import datetime
                diff = abs((datetime.fromisoformat(w.date) - datetime.fromisoformat(expected)).days)
                if diff > 1:
                    continue
            score = _score_workout_match(workout_exercises[w.id], day["type"])
            if score > best_score:
                best_score = score
                best_match = w

        min_score = 2 if best_match and len(workout_exercises.get(best_match.id, [])) >= 5 else 1
        if not best_match or best_score < min_score:
            enriched_days.append(day_data)
            continue

        used_workout_ids.add(best_match.id)
        day_data["source"] = "logged"
        day_data["status"] = "completed"
        exercises = (
            db.query(Exercise)
            .filter_by(workout_id=best_match.id)
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
