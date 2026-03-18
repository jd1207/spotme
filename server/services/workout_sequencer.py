import logging
from sqlalchemy.orm import Session
from server.models import Workout, Exercise, Set

logger = logging.getLogger(__name__)

FEEL_TO_RPE = {"easy": 6.5, "solid": 7.5, "tough": 9.0, "max": 10.0}


def create_workout_from_plan(db: Session, plan: list[dict], date: str, workout_type: str = "strength") -> dict:
    """create workout with exercises and planned sets from Claude's workout_plan array"""
    # check for existing active workout on this date
    existing = db.query(Workout).filter_by(date=date, status="active").first()
    if existing:
        # replace pending sets on existing workout
        result = replace_pending_sets(db, existing.id, plan)
        return {
            "workout_id": existing.id,
            "first_set": result["next_set"],
            "total_sets": result["total_remaining"] + _count_completed(db, existing.id),
        }

    workout = Workout(date=date, type=workout_type, status="active")
    db.add(workout)
    db.flush()

    # group plan by exercise name to create Exercise records
    exercise_map = {}
    exercise_order = 0
    for item in plan:
        name = item["exercise"]
        if name not in exercise_map:
            ex = Exercise(workout_id=workout.id, name=name, order=exercise_order)
            db.add(ex)
            db.flush()
            exercise_map[name] = ex
            exercise_order += 1

    # create Set records in plan order
    for i, item in enumerate(plan):
        ex = exercise_map[item["exercise"]]
        db.add(Set(
            exercise_id=ex.id,
            weight=item["weight"],
            reps=item["reps"],
            target_weight=item["weight"],
            target_reps=item["reps"],
            set_type=item.get("set_type", "working"),
            order=i,
            status="pending",
            completed=False,
        ))

    db.commit()
    first = get_next_set(db, workout.id)
    return {"workout_id": workout.id, "first_set": first, "total_sets": len(plan)}


def complete_set(db: Session, set_id: int, actual_weight: float, actual_reps: int, actual_rpe: float | None, feel: str | None) -> dict:
    """mark a set as completed, return next set and progress"""
    s = db.query(Set).filter_by(id=set_id).first()
    if not s:
        return {"error": "set not found"}

    s.weight = actual_weight
    s.reps = actual_reps
    s.status = "completed"
    s.completed = True

    # resolve RPE from feel or explicit value
    if actual_rpe is not None:
        s.rpe = actual_rpe
    elif feel and feel in FEEL_TO_RPE:
        s.rpe = FEEL_TO_RPE[feel]

    db.commit()

    # find workout_id through exercise
    ex = db.query(Exercise).filter_by(id=s.exercise_id).first()
    workout_id = ex.workout_id

    next_set = get_next_set(db, workout_id)
    progress = _get_progress(db, workout_id)

    # next exercise preview
    next_preview = None
    if next_set and next_set["exercise"] != ex.name:
        next_preview = f"{next_set['exercise']} {next_set['weight']}x{next_set['reps']}"

    return {
        "logged_set": {"id": s.id, "weight": s.weight, "reps": s.reps, "rpe": s.rpe, "status": s.status},
        "next_set": next_set,
        "progress": progress,
        "next_exercise_preview": next_preview,
    }


def get_next_set(db: Session, workout_id: int) -> dict | None:
    """return the next pending set for a workout, ordered by plan order"""
    row = (
        db.query(Set, Exercise)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .filter(Exercise.workout_id == workout_id, Set.status == "pending")
        .order_by(Set.order)
        .first()
    )
    if not row:
        return None
    s, ex = row
    # count which set number this is for the exercise
    set_number = (
        db.query(Set)
        .filter_by(exercise_id=ex.id, set_type=s.set_type)
        .filter(Set.order <= s.order)
        .count()
    )
    total_of_type = (
        db.query(Set)
        .filter_by(exercise_id=ex.id, set_type=s.set_type)
        .count()
    )
    return {
        "id": s.id,
        "exercise": ex.name,
        "set_type": s.set_type,
        "weight": s.target_weight or s.weight,
        "reps": s.target_reps or s.reps,
        "set_number": set_number,
        "total_of_type": total_of_type,
        "order": s.order,
    }


def replace_pending_sets(db: Session, workout_id: int, new_plan: list[dict]) -> dict:
    """delete all pending sets and replace with new plan"""
    # find all pending sets for this workout
    pending = (
        db.query(Set)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .filter(Exercise.workout_id == workout_id, Set.status == "pending")
        .all()
    )
    for s in pending:
        db.delete(s)
    db.flush()

    # find max order of completed/skipped sets
    max_order = (
        db.query(Set.order)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .filter(Exercise.workout_id == workout_id, Set.status != "pending")
        .order_by(Set.order.desc())
        .first()
    )
    start_order = (max_order[0] + 1) if max_order else 0

    # get or create exercises
    exercise_map = {}
    existing_exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    for ex in existing_exercises:
        exercise_map[ex.name] = ex
    max_ex_order = max((ex.order for ex in existing_exercises), default=-1)

    for i, item in enumerate(new_plan):
        name = item["exercise"]
        if name not in exercise_map:
            max_ex_order += 1
            ex = Exercise(workout_id=workout_id, name=name, order=max_ex_order)
            db.add(ex)
            db.flush()
            exercise_map[name] = ex
        ex = exercise_map[name]
        db.add(Set(
            exercise_id=ex.id,
            weight=item["weight"],
            reps=item["reps"],
            target_weight=item["weight"],
            target_reps=item["reps"],
            set_type=item.get("set_type", "working"),
            order=start_order + i,
            status="pending",
            completed=False,
        ))

    db.commit()
    next_set = get_next_set(db, workout_id)
    return {"next_set": next_set, "total_remaining": len(new_plan)}


def _get_progress(db: Session, workout_id: int) -> dict:
    """get completion progress for a workout"""
    all_sets = (
        db.query(Set)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .filter(Exercise.workout_id == workout_id)
        .all()
    )
    completed = sum(1 for s in all_sets if s.status == "completed")
    total = len(all_sets)
    return {"completed": completed, "total": total, "current_exercise_progress": f"{completed} of {total}"}


def _count_completed(db: Session, workout_id: int) -> int:
    return (
        db.query(Set)
        .join(Exercise, Set.exercise_id == Exercise.id)
        .filter(Exercise.workout_id == workout_id, Set.status == "completed")
        .count()
    )
