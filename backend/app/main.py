"""FastAPI application entrypoint.

Currently a skeleton with a health endpoint — enough for the test harness and
CI to have something real to exercise. Routers land in Phase 2.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="MediAgent",
    description=(
        "Agentic AI patient follow-up and healthcare assistance. "
        "Not a diagnostic device — see docs/IMPLEMENTATION_PLAN.md §6."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe. Deliberately reveals nothing about configuration."""
    return {"status": "ok", "environment": settings.environment}
