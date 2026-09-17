import asyncio
import logging
import re

import httpx
from pydantic import ValidationError

from app.clients.exceptions import (
    CepInvalidoError,
    CepNaoEncontradoError,
    ViaCepIndisponivelError,
)
from app.schemas.viacep import ViaCepResponse

logger = logging.getLogger(__name__)

_NAO_DIGITOS = re.compile(r"\D")

# Códigos que indicam problema temporário do servidor, não da requisição.
_STATUS_TEMPORARIOS = frozenset({429, 500, 502, 503, 504})


def normalizar_cep(cep: str) -> str:
    """Remove caracteres não numéricos e garante que o CEP tenha 8 dígitos."""
    digitos = _NAO_DIGITOS.sub("", cep)
    if len(digitos) != 8:
        raise CepInvalidoError(cep)
    return digitos


def _e_temporario(exc: Exception) -> bool:
    """Indica se vale a pena repetir a requisição que levantou `exc`."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _STATUS_TEMPORARIOS
    # TransportError cobre timeouts, falhas de conexão e de leitura.
    return isinstance(exc, httpx.TransportError)


def _como_indisponivel(exc: Exception) -> ViaCepIndisponivelError:
    if isinstance(exc, httpx.TimeoutException):
        return ViaCepIndisponivelError("tempo de resposta excedido")
    if isinstance(exc, ValueError):
        return ViaCepIndisponivelError("resposta não é um JSON válido")
    return ViaCepIndisponivelError(str(exc))


class ViaCepClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
        tentativas: int = 1,
        backoff_inicial: float = 0.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_client = http_client
        self._tentativas = max(1, tentativas)
        self._backoff_inicial = max(0.0, backoff_inicial)

    async def buscar(self, cep: str) -> ViaCepResponse:
        cep_normalizado = normalizar_cep(cep)
        url = f"{self._base_url}/{cep_normalizado}/json/"

        dados = await self._obter_dados(url)

        if dados.get("erro"):
            raise CepNaoEncontradoError(cep_normalizado)

        try:
            return ViaCepResponse.model_validate(dados)
        except ValidationError as exc:
            raise ViaCepIndisponivelError("resposta em formato inesperado") from exc

    async def _obter_dados(self, url: str) -> dict:
        """Busca o JSON do ViaCEP, repetindo enquanto a falha for temporária.

        A espera entre as tentativas dobra a cada repetição. Só um GET (idempotente)
        é repetido, e apenas para timeout, falha de rede ou status 429/5xx. Erros
        4xx e respostas malformadas falham de imediato, porque repeti-las não muda
        o resultado.
        """
        espera = self._backoff_inicial
        tentativa = 1

        while True:
            try:
                response = await self._get(url)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                if tentativa == self._tentativas or not _e_temporario(exc):
                    raise _como_indisponivel(exc) from exc

                logger.warning(
                    "Tentativa %d/%d ao ViaCEP falhou (%s); repetindo em %.2fs",
                    tentativa,
                    self._tentativas,
                    exc.__class__.__name__,
                    espera,
                )
                await asyncio.sleep(espera)
                espera *= 2
                tentativa += 1

    async def _get(self, url: str) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(url, timeout=self._timeout)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(url)
