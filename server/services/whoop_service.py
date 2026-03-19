from __future__ import annotations
import json
import logging
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from server.models import WhoopData, WhoopSyncQueue, Workout, Exercise, Set

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def get_whoop_client(db):
    """create a whoop client with auto-refresh from stored tokens."""
    from whoop import WhoopClient, TokenSet
    from server.models import WhoopToken

    stored = db.query(WhoopToken).first()
    if not stored:
        raise HTTPException(400, "whoop not connected — login first")

    token_set = TokenSet(
        access_token=stored.access_token,
        refresh_token=stored.refresh_token,
        expires_at=stored.expires_at.timestamp() if stored.expires_at else 0,
    )

    def persist_refreshed_tokens(new_tokens):
        stored.access_token = new_tokens.access_token
        stored.refresh_token = new_tokens.refresh_token
        stored.expires_at = datetime.fromtimestamp(new_tokens.expires_at)
        db.commit()

    return WhoopClient(
        token_set=token_set,
        on_token_refresh=persist_refreshed_tokens,
    )



async def sync_whoop_biometrics(db: Session, whoop_client):
    from whoop import WhoopAPIError

    try:
        recoveries = await whoop_client.get_recovery()
        sleeps = await whoop_client.get_sleep()
    except WhoopAPIError as e:
        logger.warning("whoop biometric sync failed: %s", e)
        return {"error": str(e), "synced": 0}

    synced = 0
    warnings = []
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

    # strain from cycles — fetched independently since scope may not be granted
    try:
        cycles = await whoop_client.get_cycles()
        for c in cycles:
            date_str = c.start[:10]
            existing = db.query(WhoopData).filter_by(date=date_str).first()
            if existing:
                existing.strain = c.strain
    except WhoopAPIError as e:
        logger.warning("whoop cycle/strain sync skipped: %s", e)
        warnings.append(f"strain unavailable: {e}")

    db.commit()
    result = {"synced": synced}
    if warnings:
        result["warnings"] = warnings
    return result


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
        return {"synced": True, "activity_id": result.activity_id}
    except WhoopAPIError as e:
        _queue_failed_sync(db, workout_id, workout.date, e)
        return {"synced": False, "error": str(e), "queued": True}


async def process_whoop_queue(db: Session):
    from whoop import WorkoutWrite, ExerciseWrite, WhoopAPIError
    from server.models import WhoopToken

    if not db.query(WhoopToken).first():
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
        client = get_whoop_client(db)
    except (ImportError, HTTPException, ValueError) as e:
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
