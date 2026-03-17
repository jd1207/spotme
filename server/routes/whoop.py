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
        from server.services.whoop_service import (
            create_whoop_client,
            sync_whoop_biometrics,
        )
        client = create_whoop_client()
        return await sync_whoop_biometrics(db, client)
    except ImportError:
        return {"error": "whoop-write-api not installed", "synced": 0}


@router.post("/whoop/retry")
async def retry_whoop_queue(db: Session = Depends(get_db)):
    if not settings.whoop_access_token:
        return {"error": "whoop not configured", "processed": 0}
    try:
        from server.services.whoop_service import process_whoop_queue
        return await process_whoop_queue(db)
    except ImportError:
        return {"error": "whoop-write-api not installed", "processed": 0}
