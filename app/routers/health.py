from fastapi import APIRouter, status

from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health_check() -> HealthResponse:
    """Report process readiness without contacting the database or OpenAI."""
    return HealthResponse()
