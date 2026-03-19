import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import WhoopToken, WhoopData

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/whoop/status")
async def whoop_status(db: Session = Depends(get_db)):
    token = db.query(WhoopToken).first()
    return {"connected": token is not None}


@router.post("/whoop/disconnect")
async def whoop_disconnect(db: Session = Depends(get_db)):
    token_row = db.query(WhoopToken).first()
    if token_row:
        db.delete(token_row)
        db.commit()
    return {"disconnected": True}


@router.post("/whoop/login")
async def whoop_login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    if not email or not password:
        return {"success": False, "error": "email and password required"}
    try:
        from whoop import CognitoAuth
    except ImportError:
        return {"success": False, "error": "whoop-write-api not installed"}
    try:
        auth = CognitoAuth()
        tokens = await auth.login(email, password)
    except Exception as e:
        return {"success": False, "error": str(e)}

    from datetime import datetime
    existing = db.query(WhoopToken).first()
    if existing:
        existing.access_token = tokens.access_token
        existing.refresh_token = tokens.refresh_token
        existing.expires_at = datetime.fromtimestamp(tokens.expires_at)
    else:
        db.add(WhoopToken(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=datetime.fromtimestamp(tokens.expires_at),
        ))
    db.commit()
    # populate exercise catalog (best-effort)
    try:
        from server.services.whoop_service import populate_exercise_catalog
        await populate_exercise_catalog(db)
    except Exception:
        pass  # catalog fetch is best-effort, login still succeeds
    return {"connected": True}


@router.get("/whoop/sync")
async def sync_whoop(db: Session = Depends(get_db)):
    token = db.query(WhoopToken).first()
    if not token:
        return {"error": "whoop not connected", "synced": 0}
    try:
        from server.services.whoop_service import sync_whoop_biometrics
        return await sync_whoop_biometrics(db, force=True)
    except ImportError:
        return {"error": "whoop-write-api not installed", "synced": 0}
    except Exception as e:
        return {"error": str(e), "synced": 0}


@router.get("/whoop/latest")
async def whoop_latest(db: Session = Depends(get_db)):
    from datetime import date
    row = db.query(WhoopData).filter_by(date=date.today().isoformat()).first()
    if not row:
        return {"data": None}
    return {
        "data": {
            "date": row.date,
            "recovery_score": row.recovery_score,
            "hrv": row.hrv,
            "resting_hr": row.resting_hr,
            "sleep_score": row.sleep_score,
            "sleep_duration": row.sleep_duration,
            "strain": row.strain,
        }
    }


@router.post("/whoop/retry")
async def retry_whoop_queue(db: Session = Depends(get_db)):
    token = db.query(WhoopToken).first()
    if not token:
        return {"error": "whoop not connected", "processed": 0}
    try:
        from server.services.whoop_service import process_whoop_queue
        return await process_whoop_queue(db)
    except ImportError:
        return {"error": "whoop-write-api not installed", "processed": 0}
