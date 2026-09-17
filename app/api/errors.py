import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.clients.exceptions import (
    CepInvalidoError,
    CepNaoEncontradoError,
    ViaCepError,
    ViaCepIndisponivelError,
)

logger = logging.getLogger(__name__)

STATUS_POR_ERRO: dict[type[ViaCepError], int] = {
    CepInvalidoError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    CepNaoEncontradoError: status.HTTP_404_NOT_FOUND,
    ViaCepIndisponivelError: status.HTTP_502_BAD_GATEWAY,
}


async def tratar_erro_viacep(request: Request, exc: ViaCepError) -> JSONResponse:
    status_code = next(
        (codigo for tipo, codigo in STATUS_POR_ERRO.items() if isinstance(exc, tipo)),
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    if status_code >= 500:
        logger.warning("%s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def registrar_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ViaCepError, tratar_erro_viacep)
