from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Workout, Exercise, Set, WhoopData

router = APIRouter()


@router.get("/progress")
async def get_progress(db: Session = Depends(get_db)):
    thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()

    # completed sets with reps 1-10 for e1rm calculation
    rows = (
        db.query(Workout.date, Set.weight, Set.reps, Exercise.name)
        .join(Exercise, Exercise.workout_id == Workout.id)
        .join(Set, Set.exercise_id == Exercise.id)
        .filter(
            Workout.date >= thirty_days_ago,
            Set.completed == True,
            Set.reps >= 1,
            Set.reps <= 10,
        )
        .order_by(Workout.date)
        .all()
    )

    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        e1rm = round(row.weight * (1 + row.reps / 30.0), 1)
        by_date[row.date].append({
            "exercise": row.name, "e1rm": e1rm,
            "weight": row.weight, "reps": row.reps,
        })

    e1rm_trend = []
    for d in sorted(by_date.keys()):
        best = max(by_date[d], key=lambda x: x["e1rm"])
        e1rm_trend.append({
            "date": d, "e1rm": best["e1rm"],
            "exercise": best["exercise"],
            "set": f"{best['weight']}x{best['reps']}",
        })

    # volume trend: total lbs moved per workout date
    volume_rows = (
        db.query(
            Workout.date,
            func.sum(Set.weight * Set.reps).label("volume"),
        )
        .join(Exercise, Exercise.workout_id == Workout.id)
        .join(Set, Set.exercise_id == Exercise.id)
        .filter(Workout.date >= thirty_days_ago, Set.completed == True)
        .group_by(Workout.date)
        .order_by(Workout.date)
        .all()
    )
    volume_trend = [
        {"date": r.date, "volume": round(r.volume)}
        for r in volume_rows
    ]

    # whoop biometric trends
    whoop_rows = (
        db.query(WhoopData)
        .filter(WhoopData.date >= thirty_days_ago)
        .order_by(WhoopData.date)
        .all()
    )
    whoop = {
        "recovery": [
            {"date": w.date, "value": w.recovery_score}
            for w in whoop_rows if w.recovery_score is not None
        ],
        "hrv": [
            {"date": w.date, "value": w.hrv}
            for w in whoop_rows if w.hrv is not None
        ],
        "strain": [
            {"date": w.date, "value": w.strain}
            for w in whoop_rows if w.strain is not None
        ],
    }

    return {
        "e1rm_trend": e1rm_trend,
        "volume_trend": volume_trend,
        "whoop": whoop,
    }


@router.get("/progress/prs")
async def get_prs(db: Session = Depends(get_db)):
    """estimated 1RM PRs per exercise using Epley formula"""
    exercise_names = [
        row[0] for row in db.query(Exercise.name).distinct().all()
    ]
    prs = []
    for name in exercise_names:
        best = (
            db.query(Set.weight, Set.reps, Workout.date)
            .join(Exercise, Set.exercise_id == Exercise.id)
            .join(Workout, Exercise.workout_id == Workout.id)
            .filter(
                Exercise.name == name,
                Set.completed == True,
                Set.reps <= 10,
                Set.reps >= 1,
            )
            .all()
        )
        if not best:
            continue
        top = max(best, key=lambda s: s.weight * (1 + s.reps / 30.0))
        e1rm = round(top.weight * (1 + top.reps / 30.0), 1)
        prs.append({
            "exercise": name, "weight": top.weight,
            "reps": top.reps, "e1rm": e1rm, "date": top.date,
        })
    prs.sort(key=lambda x: x["e1rm"], reverse=True)
    return {"prs": prs}
