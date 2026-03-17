import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from server.database import Base, engine

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app():
    app = FastAPI(title="SpotMe", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    Base.metadata.create_all(bind=engine)

    from server.routes.chat import router as chat_router
    from server.routes.workout import router as workout_router
    from server.routes.video import router as video_router
    from server.routes.profile import router as profile_router
    from server.routes.whoop import router as whoop_router
    from server.routes.progress import router as progress_router
    from server.routes.layout import router as layout_router
    from server.routes.morning import router as morning_router
    from server.routes.program import router as program_router
    app.include_router(chat_router, prefix="/api")
    app.include_router(workout_router, prefix="/api")
    app.include_router(video_router, prefix="/api")
    app.include_router(profile_router, prefix="/api")
    app.include_router(whoop_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
    app.include_router(layout_router, prefix="/api")
    app.include_router(morning_router, prefix="/api")
    app.include_router(program_router, prefix="/api")

    if FRONTEND_DIR.exists():
        # serve static assets (js, css, icons, manifest, sw)
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            # serve actual files if they exist, otherwise index.html (SPA routing)
            file_path = (FRONTEND_DIR / path).resolve()
            if path and file_path.is_relative_to(FRONTEND_DIR) and file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
