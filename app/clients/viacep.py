import re

import httpx
from pydantic import ValidationError

from app.clients.exceptions import (
    CepInvalidoError,
    CepNaoEncontradoError,
    ViaCepIndisponivelError,
)
from app.schemas.viacep import ViaCepResponse

_NAO_DIGITOS = re.compile(r"\D")


def normalizar_cep(cep: str) -> str:
    """Remove caracteres não numéricos e garante que o CEP tenha 8 dígitos."""
    digitos = _NAO_DIGITOS.sub("", cep)
    if len(digitos) != 8:
        raise CepInvalidoError(cep)
    return digitos


class ViaCepClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_client = http_client

    async def buscar(self, cep: str) -> ViaCepResponse:
        cep_normalizado = normalizar_cep(cep)
        url = f"{self._base_url}/{cep_normalizado}/json/"

        try:
            response = await self._get(url)
            response.raise_for_status()
            dados = response.json()
        except httpx.TimeoutException as exc:
            raise ViaCepIndisponivelError("tempo de resposta excedido") from exc
        except httpx.HTTPError as exc:
            raise ViaCepIndisponivelError(str(exc)) from exc
        except ValueError as exc:
            raise ViaCepIndisponivelError("resposta não é um JSON válido") from exc

        if dados.get("erro"):
            raise CepNaoEncontradoError(cep_normalizado)

        try:
            return ViaCepResponse.model_validate(dados)
        except ValidationError as exc:
            raise ViaCepIndisponivelError("resposta em formato inesperado") from exc

    async def _get(self, url: str) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(url, timeout=self._timeout)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(url)