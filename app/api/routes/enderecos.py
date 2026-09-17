from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from app.api.dependencies import EnderecoServiceDep
from app.core.security import verificar_api_key
from app.schemas.endereco import EnderecoLista, EnderecoOut, ErroResposta

router = APIRouter(
    prefix="/enderecos",
    tags=["Endereços"],
    dependencies=[Depends(verificar_api_key)],
    responses={
        401: {"model": ErroResposta, "description": "Chave de API ausente ou inválida"}
    },
)

CepPath = Annotated[
    str,
    Path(description="CEP com ou sem hífen", examples=["01001-000"]),
]

ERRO_CEP_INVALIDO = {422: {"model": ErroResposta, "description": "CEP inválido"}}
ERRO_NAO_ENCONTRADO = {
    404: {"model": ErroResposta, "description": "CEP não encontrado na base"}
}


def _nao_encontrado(cep: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"CEP {cep} não encontrado na base.",
    )


@router.post(
    "/{cep}",
    response_model=EnderecoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Extrai um endereço do ViaCEP e salva na base",
    description="Se o CEP já existir, os dados são atualizados em vez de duplicados.",
    responses={
        200: {
            "model": EnderecoOut,
            "description": "CEP já existia na base; dados atualizados",
        },
        **ERRO_CEP_INVALIDO,
        404: {"model": ErroResposta, "description": "CEP não existe no ViaCEP"},
        502: {"model": ErroResposta, "description": "ViaCEP indisponível"},
    },
)
async def importar_endereco(
    cep: CepPath, service: EnderecoServiceDep, response: Response
):
    endereco, criado = await service.importar(cep)
    if not criado:
        response.status_code = status.HTTP_200_OK
    return endereco


@router.get(
    "",
    response_model=EnderecoLista,
    summary="Lista os endereços salvos",
)
async def listar_enderecos(
    service: EnderecoServiceDep,
    uf: Annotated[
        str | None,
        Query(pattern=r"^[A-Za-z]{2}$", description="Sigla do estado", examples=["SP"]),
    ] = None,
    localidade: Annotated[
        str | None,
        Query(min_length=2, max_length=120, description="Parte do nome da cidade"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    enderecos, total = await service.listar(
        uf=uf, localidade=localidade, limit=limit, offset=offset
    )
    return EnderecoLista(
        items=[EnderecoOut.model_validate(endereco) for endereco in enderecos],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{cep}",
    response_model=EnderecoOut,
    summary="Consulta um endereço salvo",
    responses={**ERRO_CEP_INVALIDO, **ERRO_NAO_ENCONTRADO},
)
async def obter_endereco(cep: CepPath, service: EnderecoServiceDep):
    endereco = await service.obter(cep)
    if endereco is None:
        raise _nao_encontrado(cep)
    return endereco


@router.delete(
    "/{cep}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um endereço salvo",
    responses={**ERRO_CEP_INVALIDO, **ERRO_NAO_ENCONTRADO},
)
async def remover_endereco(cep: CepPath, service: EnderecoServiceDep) -> None:
    if not await service.remover(cep):
        raise _nao_encontrado(cep)
