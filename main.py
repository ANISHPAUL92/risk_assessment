"""
main.py — Application entry point.
Business logic lives in api/assess.py and api/search.py.
Constants live in config.py.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from api.assess import router as assess_router
from api.search import router as search_router
from config import STATIC_DIR

# Logging #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# App #

app = FastAPI(title="Company Risk Assessment", version="1.0.0")

# Static files (the UI)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# API routers — all endpoints live under /api/
app.include_router(assess_router, prefix="/api")
app.include_router(search_router, prefix="/api")


# UI route #

@app.get("/")
async def serve_ui() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


# Global error handlers #

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Pydantic validation errors (malformed request body) -> clean 422.
    Without this FastAPI returns a 500 with a raw Python traceback.
    """
    logger.warning("[validation] %s %s — %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for anything not handled elsewhere.
    Logs the full error server-side but never leaks a stack trace to the client.
    """
    logger.error(
        "[unhandled] %s %s — %s: %s",
        request.method, request.url, type(exc).__name__, exc,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again."},
    )


# Entrypoint #

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
