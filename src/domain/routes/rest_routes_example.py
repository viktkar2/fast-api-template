import logging
from fastapi import APIRouter, Depends
from src.domain.services.example_service import ExampleService
from src.base.core.dependencies import get_example_service
from src.domain.models.models import PrivateResponse
from src.base.auth.rbac import require_roles_and_scopes

router = APIRouter(prefix="/test", tags=["Test Auth"])
logger = logging.getLogger(__name__)


@router.get("/public")
async def public_endpoint():
    logger.info("Public endpoint accessed")
    return {"status": "success", "message": "Public endpoint accessed successfully"}


@router.get("/public/service/example")
async def public_endpoint_with_service(
    example_service: ExampleService = Depends(get_example_service),
):
    service_result = example_service.example_method()
    return {
        "status": "success",
        "message": "Public endpoint with service",
        "data": service_result,
    }


@router.get("/private")
async def private_endpoint(claims: dict = Depends(require_roles_and_scopes())):
    private_data = PrivateResponse(
        message=f"Hello, {claims.get('name', 'Authenticated User')}!", claims=claims
    )
    return {
        "status": "success",
        "data": private_data,
        "message": "Private endpoint accessed successfully",
    }
