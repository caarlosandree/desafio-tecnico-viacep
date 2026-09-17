from pydantic import BaseModel, field_validator


class ViaCepResponse(BaseModel):
    """Campos da resposta do ViaCEP."""

    cep: str
    logradouro: str = ""
    complemento: str = ""
    bairro: str = ""
    localidade: str
    uf: str
    ibge: str = ""
    ddd: str = ""

    @field_validator("cep")
    @classmethod
    def remover_hifen(cls, valor: str) -> str:
        return valor.replace("-", "")