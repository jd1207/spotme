from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import Base, engine

def create_app():
    app = FastAPI(title="SpotMe", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    Base.metadata.create_all(bind=engine)
    from server.routes.chat import router as chat_router
    from server.routes.workout import router as workout_router
    from server.routes.video import router as video_router
    from server.routes.whoop import router as whoop_router
    from server.routes.progress import router as progress_router
    from server.routes.layout import router as layout_router
    app.include_router(chat_router, prefix="/api")
    app.include_router(workout_router, prefix="/api")
    app.include_router(video_router, prefix="/api")
    app.include_router(whoop_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
    app.include_router(layout_router, prefix="/api")
    return app

app = create_app()
