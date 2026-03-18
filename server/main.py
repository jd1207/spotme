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

    # migrate new columns onto existing tables
    from sqlalchemy import text, inspect as sa_inspect
    cols = [c['name'] for c in sa_inspect(engine).get_columns('user_profiles')]
    with engine.begin() as conn:
        if 'calorie_target' not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN calorie_target INTEGER"))
        if 'protein_target' not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN protein_target INTEGER"))

    # conversation date column
    conv_cols = [c['name'] for c in sa_inspect(engine).get_columns('conversations')]
    with engine.begin() as conn:
        if 'date' not in conv_cols:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN date TEXT"))

    # set columns for workout sequencing
    set_cols = [c['name'] for c in sa_inspect(engine).get_columns('sets')]
    with engine.begin() as conn:
        if 'target_weight' not in set_cols:
            conn.execute(text("ALTER TABLE sets ADD COLUMN target_weight REAL"))
        if 'target_reps' not in set_cols:
            conn.execute(text("ALTER TABLE sets ADD COLUMN target_reps INTEGER"))
        if 'set_type' not in set_cols:
            conn.execute(text("ALTER TABLE sets ADD COLUMN set_type TEXT"))
        if 'order' not in set_cols:
            conn.execute(text('ALTER TABLE sets ADD COLUMN "order" INTEGER'))
        if 'status' not in set_cols:
            conn.execute(text("ALTER TABLE sets ADD COLUMN status TEXT"))

    # meal items column
    meal_cols = [c['name'] for c in sa_inspect(engine).get_columns('meals')]
    with engine.begin() as conn:
        if 'items' not in meal_cols:
            conn.execute(text("ALTER TABLE meals ADD COLUMN items TEXT"))

    # backfill conversation dates from created_at
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE conversations SET date = substr(created_at, 1, 10)
            WHERE date IS NULL AND created_at IS NOT NULL
        """))

    from server.routes.chat import router as chat_router
    from server.routes.workout import router as workout_router
    from server.routes.video import router as video_router
    from server.routes.profile import router as profile_router
    from server.routes.whoop import router as whoop_router
    from server.routes.progress import router as progress_router
    from server.routes.layout import router as layout_router
    from server.routes.morning import router as morning_router
    from server.routes.program import router as program_router
    from server.routes.meals import router as meals_router
    app.include_router(chat_router, prefix="/api")
    app.include_router(workout_router, prefix="/api")
    app.include_router(video_router, prefix="/api")
    app.include_router(profile_router, prefix="/api")
    app.include_router(whoop_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
    app.include_router(layout_router, prefix="/api")
    app.include_router(morning_router, prefix="/api")
    app.include_router(program_router, prefix="/api")
    app.include_router(meals_router, prefix="/api")

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
