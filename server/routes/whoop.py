from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.config import settings

router = APIRouter()

@router.get("/whoop/sync")
async def sync_whoop(db: Session = Depends(get_db)):
    if not settings.whoop_access_token:
        return {"error": "whoop not configured", "synced": 0}
    try:
        from whoop import WhoopClient
        from server.services.whoop_service import sync_whoop_biometrics
        client = WhoopClient(token=settings.whoop_access_token)
        return await sync_whoop_biometrics(db, client)
    except ImportError:
        return {"error": "whoop-write-api not installed", "synced": 0}
