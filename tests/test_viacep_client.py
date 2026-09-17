import httpx
import pytest

from app.clients.exceptions import (
    CepInvalidoError,
    CepNaoEncontradoError,
    ViaCepIndisponivelError,
)
from app.clients.viacep import ViaCepClient, normalizar_cep
from app.schemas.viacep import ViaCepResponse

BASE_URL = "https://viacep.test/ws"

RESPOSTA_SUCESSO = {
    "cep": "01001-000",
    "logradouro": "Praça da Sé",
    "complemento": "lado ímpar",
    "unidade": "",
    "bairro": "Sé",
    "localidade": "São Paulo",
    "uf": "SP",
    "estado": "São Paulo",
    "regiao": "Sudeste",
    "ibge": "3550308",
    "gia": "1004",
    "ddd": "11",
    "siafi": "7107",
}


def criar_cliente(handler) -> ViaCepClient:
    transport = httpx.MockTransport(handler)
    return ViaCepClient(
        base_url=BASE_URL,
        timeout=1.0,
        http_client=httpx.AsyncClient(transport=transport),
    )


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("01001000", "01001000"),
        ("01001-000", "01001000"),
        (" 01.001-000 ", "01001000"),
    ],
)
def test_normalizar_cep_aceita_formatos_validos(entrada, esperado):
    assert normalizar_cep(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "123", "0100100", "010010000", "abcdefgh"])
def test_normalizar_cep_rejeita_formatos_invalidos(entrada):
    with pytest.raises(CepInvalidoError):
        normalizar_cep(entrada)


@pytest.mark.anyio
async def test_buscar_retorna_endereco():
    urls_chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls_chamadas.append(str(request.url))
        return httpx.Response(200, json=RESPOSTA_SUCESSO)

    endereco = await criar_cliente(handler).buscar("01001-000")

    assert urls_chamadas == [f"{BASE_URL}/01001000/json/"]
    assert isinstance(endereco, ViaCepResponse)
    assert endereco.cep == "01001000"
    assert endereco.localidade == "São Paulo"
    assert endereco.uf == "SP"


@pytest.mark.anyio
@pytest.mark.parametrize("cep", ["123", "abcdefgh"])
async def test_buscar_cep_invalido_nao_chama_api(cep):
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(200, json=RESPOSTA_SUCESSO)

    with pytest.raises(CepInvalidoError):
        await criar_cliente(handler).buscar(cep)

    assert chamadas == []


@pytest.mark.anyio
@pytest.mark.parametrize("valor_erro", ["true", True])
async def test_buscar_cep_inexistente(valor_erro):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"erro": valor_erro})

    with pytest.raises(CepNaoEncontradoError):
        await criar_cliente(handler).buscar("99999999")


@pytest.mark.anyio
async def test_buscar_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(ViaCepIndisponivelError, match="tempo de resposta"):
        await criar_cliente(handler).buscar("01001000")


@pytest.mark.anyio
async def test_buscar_erro_de_conexao():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem conexão", request=request)

    with pytest.raises(ViaCepIndisponivelError):
        await criar_cliente(handler).buscar("01001000")


@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 500, 503])
async def test_buscar_status_de_erro(status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    with pytest.raises(ViaCepIndisponivelError):
        await criar_cliente(handler).buscar("01001000")


@pytest.mark.anyio
async def test_buscar_resposta_nao_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>erro</html>")

    with pytest.raises(ViaCepIndisponivelError, match="JSON"):
        await criar_cliente(handler).buscar("01001000")


@pytest.mark.anyio
async def test_buscar_resposta_sem_campos_obrigatorios():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"cep": "01001-000"})

    with pytest.raises(ViaCepIndisponivelError, match="formato inesperado"):
        await criar_cliente(handler).buscar("01001000")
