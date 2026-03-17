import secrets
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from server.database import get_db
from server.config import settings
from server.models import WhoopToken

router = APIRouter()

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
REDIRECT_URI = "https://steamdeck.tail704a86.ts.net/api/whoop/callback"

# in-memory state for CSRF protection (single user, fine for this)
_oauth_state: str = ""


def _get_token(db: Session) -> WhoopToken | None:
    return db.query(WhoopToken).first()


def _get_access_token(db: Session) -> str | None:
    # prefer DB token, fall back to .env
    token_row = _get_token(db)
    if token_row:
        return token_row.access_token
    if settings.whoop_access_token:
        return settings.whoop_access_token
    return None


@router.get("/whoop/status")
async def whoop_status(db: Session = Depends(get_db)):
    token = _get_access_token(db)
    configured = settings.whoop_client_id and settings.whoop_client_secret
    return {
        "connected": token is not None,
        "oauth_available": configured,
    }


@router.get("/whoop/authorize")
async def whoop_authorize():
    global _oauth_state
    if not settings.whoop_client_id:
        return {"error": "whoop client_id not configured in .env"}
    _oauth_state = secrets.token_urlsafe(32)
    params = (
        f"?client_id={settings.whoop_client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=read:recovery read:sleep read:workout read:profile read:body_measurement"
        f"&state={_oauth_state}"
    )
    return {"url": f"{WHOOP_AUTH_URL}{params}"}


@router.get("/whoop/callback")
async def whoop_callback(code: str, state: str, db: Session = Depends(get_db)):
    global _oauth_state
    if state != _oauth_state:
        return RedirectResponse("/?whoop=error&reason=invalid_state")
    _oauth_state = ""
    try:
        from whoop.auth import WhoopAuth
        auth = WhoopAuth(
            client_id=settings.whoop_client_id,
            client_secret=settings.whoop_client_secret,
        )
        await auth.exchange_code(code, REDIRECT_URI)
        # store tokens in DB
        token_row = _get_token(db)
        if token_row:
            token_row.access_token = auth.access_token
            token_row.refresh_token = auth.refresh_token
        else:
            db.add(WhoopToken(
                access_token=auth.access_token,
                refresh_token=auth.refresh_token,
            ))
        db.commit()
        return RedirectResponse("/?whoop=connected")
    except ImportError:
        return RedirectResponse("/?whoop=error&reason=library_missing")
    except Exception as e:
        return RedirectResponse(f"/?whoop=error&reason={str(e)[:50]}")


@router.get("/whoop/sync")
async def sync_whoop(db: Session = Depends(get_db)):
    access_token = _get_access_token(db)
    if not access_token:
        return {"error": "whoop not connected", "synced": 0}
    try:
        from whoop import WhoopClient
        from server.services.whoop_service import sync_whoop_biometrics
        client = WhoopClient(token=access_token)
        return await sync_whoop_biometrics(db, client)
    except ImportError:
        return {"error": "whoop-write-api not installed", "synced": 0}


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
