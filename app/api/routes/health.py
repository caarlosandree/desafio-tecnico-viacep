from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import SessionDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Verifica se a API e o banco estão respondendo",
    responses={503: {"model": HealthResponse, "description": "Banco indisponível"}},
)
async def health(session: SessionDep, response: Response) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degradado", banco="indisponível")
    return HealthResponse(status="ok", banco="ok")
