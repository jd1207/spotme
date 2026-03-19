from fastapi import APIRouter
from server.services.claude_service import ClaudeService

router = APIRouter()


@router.post("/interview/questions")
async def generate_interview_questions(data: dict):
    """generate personalized interview questions based on profile."""
    service = ClaudeService()
    profile_summary = (
        f"Name: {data.get('name', 'athlete')}, "
        f"Experience: {data.get('experience', 'unknown')}, "
        f"Goal: {data.get('goals', 'general fitness')}, "
        f"Frequency: {data.get('frequency', '3x/week')}, "
        f"Equipment: {data.get('equipment', 'full gym')}"
    )
    questions = await service.generate_interview_questions(profile_summary)
    return {"questions": questions}
