from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.database import Base, engine

def create_app():
    app = FastAPI(title="SpotMe", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    Base.metadata.create_all(bind=engine)
    from server.routes.chat import router as chat_router
    from server.routes.workout import router as workout_router
    app.include_router(chat_router, prefix="/api")
    app.include_router(workout_router, prefix="/api")
    return app

app = create_app()
