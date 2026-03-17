import logging
import secrets
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from server.database import get_db
from server.config import settings
from server.models import WhoopToken, WhoopData, SystemMemory

logger = logging.getLogger(__name__)

router = APIRouter()

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
REDIRECT_URI = "https://steamdeck.tail704a86.ts.net/api/whoop/callback"


def _get_token(db: Session) -> WhoopToken | None:
    return db.query(WhoopToken).first()


def _get_access_token(db: Session) -> str | None:
    token_row = _get_token(db)
    if token_row:
        return token_row.access_token
    if settings.whoop_access_token:
        return settings.whoop_access_token
    return None


async def _refresh_token(db: Session) -> str | None:
    """refresh the OAuth token if a refresh_token is stored"""
    token_row = _get_token(db)
    if not token_row or not token_row.refresh_token:
        return None
    if not settings.whoop_client_id or not settings.whoop_client_secret:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(base_url="https://api.prod.whoop.com") as client:
            resp = await client.post(
                "/oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token_row.refresh_token,
                    "client_id": settings.whoop_client_id,
                    "client_secret": settings.whoop_client_secret,
                },
            )
        if resp.status_code != 200:
            logger.warning("token refresh failed: %s %s", resp.status_code, resp.text)
            return None
        data = resp.json()
        token_row.access_token = data["access_token"]
        if data.get("refresh_token"):
            token_row.refresh_token = data["refresh_token"]
        db.commit()
        logger.info("whoop token refreshed")
        return token_row.access_token
    except Exception as e:
        logger.warning("token refresh error: %s", e)
        return None


async def _get_valid_token(db: Session) -> str | None:
    """get a valid token, refreshing if needed"""
    token = _get_access_token(db)
    if not token:
        return None
    # quick test: hit profile endpoint to check if token works
    try:
        import httpx
        async with httpx.AsyncClient(base_url="https://api.prod.whoop.com") as client:
            resp = await client.get(
                "/developer/v2/user/profile/basic",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            return token
        logger.info("token expired (status %d), attempting refresh", resp.status_code)
    except Exception:
        pass
    refreshed = await _refresh_token(db)
    return refreshed


def _set_oauth_state(db: Session, state: str):
    row = db.query(SystemMemory).filter_by(key="whoop_oauth_state").first()
    if row:
        row.content = state
    else:
        db.add(SystemMemory(key="whoop_oauth_state", content=state))
    db.commit()


def _get_oauth_state(db: Session) -> str:
    row = db.query(SystemMemory).filter_by(key="whoop_oauth_state").first()
    return row.content if row else ""


def _get_write_token(db: Session) -> str | None:
    row = db.query(SystemMemory).filter_by(key="whoop_write_token").first()
    return row.content if row and row.content else None


def _set_write_token(db: Session, token: str):
    row = db.query(SystemMemory).filter_by(key="whoop_write_token").first()
    if row:
        row.content = token
    else:
        db.add(SystemMemory(key="whoop_write_token", content=token))
    db.commit()


@router.get("/whoop/status")
async def whoop_status(db: Session = Depends(get_db)):
    token = _get_access_token(db)
    configured = bool(settings.whoop_client_id and settings.whoop_client_secret)
    write_token = _get_write_token(db)
    return {
        "connected": token is not None,
        "oauth_available": configured,
        "write_enabled": write_token is not None,
    }


@router.get("/whoop/authorize")
async def whoop_authorize(db: Session = Depends(get_db)):
    if not settings.whoop_client_id:
        return {"error": "whoop client_id not configured in .env"}
    state = secrets.token_urlsafe(32)
    _set_oauth_state(db, state)
    params = (
        f"?client_id={settings.whoop_client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=offline read:recovery read:sleep read:workout read:cycles read:profile read:body_measurement"
        f"&state={state}"
    )
    return {"url": f"{WHOOP_AUTH_URL}{params}"}


@router.get("/whoop/callback")
async def whoop_callback(code: str, state: str, db: Session = Depends(get_db)):
    logger.info(f"whoop callback hit: code={code[:10]}..., state={state[:10]}...")
    expected = _get_oauth_state(db)
    logger.info(f"expected state: {expected[:10] if expected else 'EMPTY'}...")
    if not expected or state != expected:
        logger.error(f"state mismatch: got={state[:10]}, expected={expected[:10] if expected else 'EMPTY'}")
        return RedirectResponse("/?whoop=error&reason=invalid_state")
    _set_oauth_state(db, "")
    try:
        import httpx
        logger.info("exchanging code for token...")
        async with httpx.AsyncClient(base_url="https://api.prod.whoop.com") as client:
            resp = await client.post(
                "/oauth/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": settings.whoop_client_id,
                    "client_secret": settings.whoop_client_secret,
                },
            )
        if resp.status_code != 200:
            logger.error(f"token exchange failed: {resp.status_code} {resp.text}")
            return RedirectResponse(f"/?whoop=error&reason=token_exchange_{resp.status_code}")
        data = resp.json()
        logger.info(f"token exchange successful, keys: {list(data.keys())}")
        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        token_row = _get_token(db)
        if token_row:
            token_row.access_token = access_token
            token_row.refresh_token = refresh_token
        else:
            db.add(WhoopToken(
                access_token=access_token,
                refresh_token=refresh_token,
            ))
        db.commit()
        logger.info("whoop connected successfully")
        return RedirectResponse("/?whoop=connected")
    except ImportError:
        logger.error("httpx not installed")
        return RedirectResponse("/?whoop=error&reason=library_missing")
    except Exception as e:
        logger.error(f"whoop callback error: {e}")
        return RedirectResponse(f"/?whoop=error&reason={str(e)[:50]}")


@router.post("/whoop/disconnect")
async def whoop_disconnect(db: Session = Depends(get_db)):
    token_row = _get_token(db)
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
        from whoop.auth import WhoopAuth, WhoopAuthError
    except ImportError:
        return {"success": False, "error": "whoop-write-api not installed"}
    try:
        auth = WhoopAuth()
        token = await auth.login_password(email, password)
        _set_write_token(db, token)
        logger.info("whoop write token obtained via password login")
        return {"success": True}
    except WhoopAuthError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning("whoop login failed: %s", e)
        return {"success": False, "error": str(e)}


@router.get("/whoop/sync")
async def sync_whoop(db: Session = Depends(get_db)):
    access_token = await _get_valid_token(db)
    if not access_token:
        return {"error": "whoop not connected (token expired — disconnect and reconnect)", "synced": 0}
    try:
        from whoop import WhoopClient
        from server.services.whoop_service import sync_whoop_biometrics
        client = WhoopClient(token=access_token)
        return await sync_whoop_biometrics(db, client)
    except ImportError:
        return {"error": "whoop-write-api not installed", "synced": 0}


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


@router.post("/whoop/test-write")
async def whoop_test_write(db: Session = Depends(get_db)):
    write_token = _get_write_token(db)
    if not write_token:
        return {"success": False, "error": "Enter your Whoop login below to enable writes"}
    try:
        from datetime import datetime, timezone, timedelta
        from whoop import WhoopClient, WorkoutWrite, WhoopAPIError
    except ImportError:
        return {"success": False, "error": "whoop-write-api not installed"}
    try:
        now = datetime.now(timezone.utc)
        start = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end = (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        client = WhoopClient(token=write_token)
        workout = WorkoutWrite(sport_id=128, start=start, end=end)
        result = await client.log_workout(workout)
        return {
            "success": True,
            "activity_id": result.activity_id,
            "sport": "stretching",
            "duration_min": 1,
        }
    except WhoopAPIError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/whoop/retry")
async def retry_whoop_queue(db: Session = Depends(get_db)):
    access_token = _get_access_token(db)
    if not access_token:
        return {"error": "whoop not connected", "processed": 0}
    try:
        from server.services.whoop_service import process_whoop_queue
        return await process_whoop_queue(db)
    except ImportError:
        return {"error": "whoop-write-api not installed", "processed": 0}
