from __future__ import annotations
import json
from sqlalchemy.orm import Session
from server.models import WhoopData, WhoopSyncQueue, Workout, Exercise, Set

async def sync_whoop_biometrics(db, whoop_client):
    recoveries = await whoop_client.get_recovery()
    sleeps = await whoop_client.get_sleep()
    synced = 0
    for r in recoveries:
        existing = db.query(WhoopData).filter_by(date=r.created_at[:10]).first()
        if not existing:
            db.add(WhoopData(date=r.created_at[:10], recovery_score=r.recovery_score, hrv=r.hrv, resting_hr=int(r.resting_hr)))
            synced += 1
    for s in sleeps:
        existing = db.query(WhoopData).filter_by(date=s.created_at[:10]).first()
        if existing:
            existing.sleep_score = s.performance
            existing.sleep_duration = s.total_in_bed_hours
    db.commit()
    return {"synced": synced}

async def push_workout_to_whoop(db, whoop_client, workout_id):
    workout = db.query(Workout).filter_by(id=workout_id).first()
    if not workout:
        return {"error": "workout not found"}
    exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    try:
        from whoop import WorkoutWrite, ExerciseWrite
        exercise_writes = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            if sets:
                exercise_writes.append(ExerciseWrite(name=ex.name, sets=len(sets), reps=sets[0].reps, weight=sets[0].weight))
        whoop_workout = WorkoutWrite(sport_id=1, start=f"{workout.date}T00:00:00.000Z", end=f"{workout.date}T01:00:00.000Z", exercises=exercise_writes)
        result = await whoop_client.log_workout(whoop_workout)
        return {"synced": True, "activity_id": result["activity_id"]}
    except Exception as e:
        db.add(WhoopSyncQueue(workout_id=workout_id, payload=json.dumps({"date": workout.date}), status="pending", last_error=str(e)))
        db.commit()
        return {"synced": False, "error": str(e), "queued": True}
