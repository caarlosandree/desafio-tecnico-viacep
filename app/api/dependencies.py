from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.viacep import ViaCepClient
from app.core.config import get_settings
from app.db.session import get_session
from app.services.endereco_service import EnderecoService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_viacep_client(request: Request) -> ViaCepClient:
    settings = get_settings()
    return ViaCepClient(
        base_url=settings.viacep_base_url,
        timeout=settings.http_timeout,
        http_client=getattr(request.app.state, "http_client", None),
    )


ViaCepClientDep = Annotated[ViaCepClient, Depends(get_viacep_client)]


async def get_endereco_service(
    session: SessionDep, viacep: ViaCepClientDep
) -> EnderecoService:
    return EnderecoService(session, viacep)


EnderecoServiceDep = Annotated[EnderecoService, Depends(get_endereco_service)]
