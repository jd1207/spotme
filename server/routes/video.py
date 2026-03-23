import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import FormCheck
from server.services.video_service import VideoService
from server.services.claude_service import ClaudeService
from server.schemas import VideoAnalysisResponse
from server.config import settings

router = APIRouter()

@router.post("/video", response_model=VideoAnalysisResponse)
async def analyze_video(file: UploadFile = File(...), exercise: str = "unknown exercise", weight: float = 0, set_number: int = 0, db: Session = Depends(get_db)):
    video_service = VideoService(video_dir=settings.video_dir)
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    video_path = await video_service.save_upload(await file.read(), filename)
    frames = await video_service.extract_frames(video_path, num_frames=3)
    context = f"{exercise} at {weight}lbs, set {set_number}"
    claude = ClaudeService()
    result = await claude.analyze_form(frames, context)
    form_check = FormCheck(video_path=video_path, frames_extracted=len(frames), claude_analysis=result["analysis"])
    db.add(form_check)
    db.commit()
    return VideoAnalysisResponse(analysis=result["analysis"])
