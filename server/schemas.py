from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    workout_id: int | None = None
    date: str | None = None

class ChatResponse(BaseModel):
    response: str
    layout: dict | None = None
    set_suggestion: dict | None = None

class SetLog(BaseModel):
    exercise_name: str
    weight: float
    reps: int
    rpe: float | None = None
    notes: str | None = None

class WorkoutCompleteRequest(BaseModel):
    workout_id: int

class WorkoutCompleteResponse(BaseModel):
    status: str
    whoop_synced: bool
    whoop_error: str | None = None

class VideoAnalysisResponse(BaseModel):
    analysis: str
    flagged_issues: list[str] | None = None

class LayoutResponse(BaseModel):
    screen: str
    layout: list[dict]

class ProgressResponse(BaseModel):
    bench_1rm_trend: list[dict]
    volume_trend: list[dict]
    whoop_trends: dict
