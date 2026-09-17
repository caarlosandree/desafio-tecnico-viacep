import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

API_KEY_HEADER = "X-API-Key"

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    description="Chave de acesso definida na variável de ambiente `API_KEY`.",
    auto_error=False,
)


async def verificar_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    esperada = settings.api_key.get_secret_value()
    # compare_digest evita que o tempo de resposta revele parte da chave.
    if api_key is None or not secrets.compare_digest(
        api_key.encode(), esperada.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
