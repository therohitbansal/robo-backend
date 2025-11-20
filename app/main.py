from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import apis, websites, robot


def create_app() -> FastAPI:
    app = FastAPI(title="Nouveau QA Control Center (NQCC)", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

    app.include_router(apis.router, prefix="/api-monitor", tags=["api-monitor"])
    app.include_router(websites.router, prefix="/websites", tags=["websites"])
    app.include_router(robot.router, prefix="/robot", tags=["robot"])

    # Serve artifacts: /files/robot_runs/<id>/...
    app.mount("/files", StaticFiles(directory="./data", html=True), name="files")

    @app.get("/healthz")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
