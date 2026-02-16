import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"], prefix="")
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(request: Request):
    """
    Health check endpoint.
    Returns 200 OK if the service is healthy, including database connectivity status.
    """
    result = {"status": "Healthy", "message": "Service is up and running."}

    if hasattr(request.app.state, "db_client"):
        try:
            await request.app.state.db_client.admin.command("ping")
            result["database"] = "connected"
        except Exception:
            logger.exception("Database health check failed")
            result["database"] = "unavailable"
            result["status"] = "Degraded"

    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        result["redis"] = "not configured"
    else:
        try:
            await redis_client.ping()
            result["redis"] = "connected"
        except Exception:
            logger.exception("Redis health check failed")
            result["redis"] = "unavailable"
            result["status"] = "Degraded"

    return JSONResponse(status_code=200, content=result)


@router.get("/")
async def health_v2():
    """
    Health check endpoint.
    This endpoint returns 200 OK if the service is healthy.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "Healthy", "message": "Service is up and running."},
    )
