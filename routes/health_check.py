from fastapi import APIRouter
from models import HealthCheckResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthCheckResponse, summary="Check API health")
def health_check():
    return HealthCheckResponse(status="healthy")
