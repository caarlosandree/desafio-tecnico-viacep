from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnderecoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cep: str
    logradouro: str
    complemento: str
    bairro: str
    localidade: str
    uf: str
    ibge: str
    ddd: str
    created_at: datetime
    updated_at: datetime


class EnderecoLista(BaseModel):
    items: list[EnderecoOut]
    total: int
    limit: int
    offset: int


class ErroResposta(BaseModel):
    detail: str
