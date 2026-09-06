# src/api/app.py
# FastAPI application factory, middleware configuration, and static file mounting.
# Connects to: src/config.py, src/api/routes.py
# Created: 2026-09-06

import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.api.routes import router as api_router
from src.config import settings

# Configure structured root logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("store_locator")


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI web application."""
    app = FastAPI(
        title="Google Maps Store Locator API",
        description="High-performance store locator with nearest store search, turn-by-turn directions, real-time operating hours, and customer ratings.",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API endpoints
    app.include_router(api_router)

    # Mount static assets if directory exists
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            """Serve the single-page interactive Store Locator map UI."""
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return FileResponse(str(static_dir / "index.html"))

    logger.info("Store Locator API application successfully configured.")
    return app


app = create_app()
