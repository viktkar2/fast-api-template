from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"], prefix="")


@router.get("/health")
async def health():
    """
    Health check endpoint.
    This endpoint returns 200 OK if the service is healthy.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "Healthy", "message": "Service is up and running."},
    )
    
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

