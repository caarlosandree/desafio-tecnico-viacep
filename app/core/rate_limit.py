"""Limite de requisições por cliente, mantido na memória do processo."""

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class Veredito:
    permitido: bool
    restantes: int
    espera: float  # segundos até a requisição mais antiga sair da janela


class LimitadorDeTaxa:
    """Janela deslizante: guarda o instante das requisições recentes de cada cliente.

    O estado vive no processo. Com mais de um worker ou réplica, cada um aplica o
    próprio limite. Para valer no conjunto, o contador precisaria ficar em um Redis
    ou na borda (proxy reverso, API gateway).
    """

    def __init__(
        self,
        limite: int,
        janela: float,
        agora: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limite = limite
        self._janela = janela
        self._agora = agora
        self._historico: defaultdict[str, deque[float]] = defaultdict(deque)
        self._proxima_limpeza = agora() + janela

    @property
    def clientes(self) -> int:
        """Quantos clientes estão sendo acompanhados no momento."""
        return len(self._historico)

    def registrar(self, chave: str) -> Veredito:
        """Contabiliza uma requisição do cliente `chave` e diz se ela cabe no limite."""
        agora = self._agora()
        limiar = agora - self._janela

        historico = self._historico[chave]
        while historico and historico[0] <= limiar:
            historico.popleft()

        if len(historico) >= self._limite:
            # A vaga mais próxima abre quando a requisição mais antiga vence.
            return Veredito(False, 0, historico[0] - limiar)

        historico.append(agora)
        self._descartar_ociosos(agora, limiar)
        return Veredito(True, self._limite - len(historico), 0.0)

    def _descartar_ociosos(self, agora: float, limiar: float) -> None:
        """Esquece clientes parados, para o dicionário não crescer sem limite."""
        if agora < self._proxima_limpeza:
            return

        ociosos = [
            chave
            for chave, historico in self._historico.items()
            if not historico or historico[-1] <= limiar
        ]
        for chave in ociosos:
            del self._historico[chave]

        self._proxima_limpeza = agora + self._janela


def _identificar(request: Request) -> str:
    """Chave do cliente. Atrás de proxy, o uvicorn roda com --proxy-headers e o
    `request.client` já reflete o X-Forwarded-For."""
    return request.client.host if request.client else "desconhecido"


def _obter_limitador(request: Request, settings: Settings) -> LimitadorDeTaxa:
    limitador = getattr(request.app.state, "limitador", None)
    if limitador is None:
        limitador = LimitadorDeTaxa(
            settings.rate_limit_requisicoes, settings.rate_limit_janela
        )
        request.app.state.limitador = limitador
    return limitador


async def limitar_taxa(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    limite = settings.rate_limit_requisicoes
    if limite <= 0:  # 0 desliga o limite
        return

    veredito = _obter_limitador(request, settings).registrar(_identificar(request))
    cabecalhos = {
        "X-RateLimit-Limit": str(limite),
        "X-RateLimit-Remaining": str(veredito.restantes),
    }

    if not veredito.permitido:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de requisições excedido. Tente de novo em instantes.",
            headers={**cabecalhos, "Retry-After": str(max(1, ceil(veredito.espera)))},
        )

    response.headers.update(cabecalhos)
