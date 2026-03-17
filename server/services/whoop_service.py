from __future__ import annotations
import json
import logging
from sqlalchemy.orm import Session
from server.models import WhoopData, WhoopSyncQueue, Workout, Exercise, Set
from server.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def create_whoop_client():
    # lazy import — whoop-write-api may not be installed
    from whoop import WhoopClient
    from whoop.auth import WhoopAuth

    if settings.whoop_client_id and settings.whoop_client_secret:
        auth = WhoopAuth(
            client_id=settings.whoop_client_id,
            client_secret=settings.whoop_client_secret,
        )
        auth.access_token = settings.whoop_access_token
        return WhoopClient(auth=auth)
    return WhoopClient(token=settings.whoop_access_token)


async def sync_whoop_biometrics(db: Session, whoop_client):
    from whoop import WhoopAPIError

    try:
        recoveries = await whoop_client.get_recovery()
        sleeps = await whoop_client.get_sleep()
    except WhoopAPIError as e:
        logger.warning("whoop biometric sync failed: %s", e)
        return {"error": str(e), "synced": 0}

    synced = 0
    for r in recoveries:
        date_str = r.created_at[:10]
        existing = db.query(WhoopData).filter_by(date=date_str).first()
        if not existing:
            db.add(WhoopData(
                date=date_str,
                recovery_score=r.recovery_score,
                hrv=r.hrv,
                resting_hr=int(r.resting_hr),
            ))
            synced += 1
    for s in sleeps:
        date_str = s.created_at[:10]
        existing = db.query(WhoopData).filter_by(date=date_str).first()
        if existing:
            existing.sleep_score = s.performance
            existing.sleep_duration = s.total_in_bed_hours
    db.commit()
    return {"synced": synced}


async def push_workout_to_whoop(db: Session, whoop_client, workout_id: int):
    from whoop import WorkoutWrite, ExerciseWrite, WhoopAPIError

    workout = db.query(Workout).filter_by(id=workout_id).first()
    if not workout:
        return {"synced": False, "error": "workout not found"}

    exercises = db.query(Exercise).filter_by(workout_id=workout_id).all()
    exercise_writes = []
    for ex in exercises:
        sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
        if sets:
            exercise_writes.append(ExerciseWrite(
                name=ex.name,
                sets=len(sets),
                reps=sets[0].reps,
                weight=sets[0].weight,
            ))

    # use actual duration if available, default to 1 hour
    duration_mins = workout.duration or 60
    start_ts = f"{workout.date}T12:00:00.000Z"
    end_hour = 12 + (duration_mins // 60)
    end_min = duration_mins % 60
    end_ts = f"{workout.date}T{end_hour:02d}:{end_min:02d}:00.000Z"

    whoop_workout = WorkoutWrite(
        sport_id=1,
        start=start_ts,
        end=end_ts,
        exercises=exercise_writes,
    )

    try:
        result = await whoop_client.log_workout(whoop_workout)
        return {"synced": True, "activity_id": result["activity_id"]}
    except WhoopAPIError as e:
        _queue_failed_sync(db, workout_id, workout.date, e)
        return {"synced": False, "error": str(e), "queued": True}


async def process_whoop_queue(db: Session):
    from whoop import WorkoutWrite, ExerciseWrite, WhoopAPIError

    if not settings.whoop_access_token:
        return {"processed": 0, "error": "whoop not configured"}

    pending = (
        db.query(WhoopSyncQueue)
        .filter(WhoopSyncQueue.status == "pending")
        .filter(WhoopSyncQueue.retries < MAX_RETRIES)
        .all()
    )
    if not pending:
        return {"processed": 0}

    try:
        client = create_whoop_client()
    except (ImportError, ValueError) as e:
        return {"processed": 0, "error": str(e)}

    processed = 0
    for item in pending:
        workout = db.query(Workout).filter_by(id=item.workout_id).first()
        if not workout:
            item.status = "failed"
            item.last_error = "workout deleted"
            continue

        exercises = db.query(Exercise).filter_by(workout_id=workout.id).all()
        exercise_writes = []
        for ex in exercises:
            sets = db.query(Set).filter_by(exercise_id=ex.id, completed=True).all()
            if sets:
                exercise_writes.append(ExerciseWrite(
                    name=ex.name,
                    sets=len(sets),
                    reps=sets[0].reps,
                    weight=sets[0].weight,
                ))

        duration_mins = workout.duration or 60
        start_ts = f"{workout.date}T12:00:00.000Z"
        end_hour = 12 + (duration_mins // 60)
        end_min = duration_mins % 60
        end_ts = f"{workout.date}T{end_hour:02d}:{end_min:02d}:00.000Z"

        whoop_workout = WorkoutWrite(
            sport_id=1,
            start=start_ts,
            end=end_ts,
            exercises=exercise_writes,
        )

        try:
            await client.log_workout(whoop_workout)
            item.status = "synced"
            processed += 1
        except WhoopAPIError as e:
            item.retries += 1
            item.last_error = str(e)
            if item.retries >= MAX_RETRIES:
                item.status = "failed"
            logger.warning(
                "whoop queue retry %d/%d for workout %d: %s",
                item.retries, MAX_RETRIES, item.workout_id, e,
            )

    db.commit()
    return {"processed": processed, "remaining": len(pending) - processed}


def _queue_failed_sync(db: Session, workout_id: int, date: str, error: Exception):
    db.add(WhoopSyncQueue(
        workout_id=workout_id,
        payload=json.dumps({"date": date}),
        status="pending",
        last_error=str(error),
    ))
    db.commit()
    logger.info("queued failed whoop sync for workout %d", workout_id)
