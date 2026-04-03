from fastapi import APIRouter
from models import HealthCheckResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthCheckResponse, summary="Check API health")
@router.get("/health_check", include_in_schema=False, response_model=HealthCheckResponse)
def health_check():
    return HealthCheckResponse(status="healthy")
