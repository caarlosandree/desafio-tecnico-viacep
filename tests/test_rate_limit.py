import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.dependencies import get_endereco_service
from app.core.config import get_settings
from app.core.rate_limit import LimitadorDeTaxa
from app.core.security import API_KEY_HEADER
from app.db.session import get_session
from app.main import app
from app.services.endereco_service import EnderecoService

pytestmark = pytest.mark.anyio

URL = "/api/v1/enderecos"
API_KEY_TESTE = "chave-de-teste"
LIMITE = 3
JANELA = 60.0


class RelogioFalso:
    """Relógio controlado pelo teste, no lugar do time.monotonic."""

    def __init__(self) -> None:
        self.instante = 0.0

    def __call__(self) -> float:
        return self.instante

    def avancar(self, segundos: float) -> None:
        self.instante += segundos


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso()


def criar_client(ip: str = "127.0.0.1") -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, client=(ip, 12345)),
        base_url="http://test",
        headers={API_KEY_HEADER: API_KEY_TESTE},
    )


@pytest.fixture
async def client(session, viacep, relogio):
    """Cliente autenticado, com limite baixo e relógio controlado pelo teste."""
    settings_teste = get_settings().model_copy(
        update={
            "api_key": SecretStr(API_KEY_TESTE),
            "rate_limit_requisicoes": LIMITE,
            "rate_limit_janela": JANELA,
        }
    )
    app.dependency_overrides[get_settings] = lambda: settings_teste
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_endereco_service] = lambda: EnderecoService(
        session, viacep
    )
    app.state.limitador = LimitadorDeTaxa(LIMITE, JANELA, agora=relogio)

    async with criar_client() as client:
        yield client

    app.dependency_overrides.clear()
    app.state.limitador = None


async def esgotar_limite(client: AsyncClient) -> None:
    for _ in range(LIMITE):
        assert (await client.get(URL)).status_code == 200


# ---------- Comportamento pela API ----------


async def test_requisicoes_dentro_do_limite_passam(client):
    restantes = []
    for _ in range(LIMITE):
        response = await client.get(URL)
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == str(LIMITE)
        restantes.append(response.headers["X-RateLimit-Remaining"])

    assert restantes == ["2", "1", "0"]


async def test_requisicao_excedente_recebe_429(client):
    await esgotar_limite(client)

    response = await client.get(URL)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(int(JANELA))
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "Limite de requisições excedido" in response.json()["detail"]


async def test_limite_vale_para_todos_os_metodos(client):
    await esgotar_limite(client)

    assert (await client.post(f"{URL}/01001-000")).status_code == 429
    assert (await client.delete(f"{URL}/01001-000")).status_code == 429


async def test_janela_expirada_libera_o_cliente(client, relogio):
    await esgotar_limite(client)
    assert (await client.get(URL)).status_code == 429

    relogio.avancar(JANELA + 1)

    assert (await client.get(URL)).status_code == 200


async def test_clientes_de_ips_diferentes_nao_se_atrapalham(client):
    await esgotar_limite(client)
    assert (await client.get(URL)).status_code == 429

    async with criar_client(ip="10.0.0.7") as outro:
        assert (await outro.get(URL)).status_code == 200


async def test_health_fica_fora_do_limite(client):
    await esgotar_limite(client)
    assert (await client.get(URL)).status_code == 429

    for _ in range(3):
        response = await client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers


async def test_limitador_nasce_das_configuracoes_na_primeira_requisicao(client):
    # Em produção ninguém monta o limitador: ele é criado na primeira requisição.
    app.state.limitador = None

    response = await client.get(URL)

    assert response.status_code == 200
    assert isinstance(app.state.limitador, LimitadorDeTaxa)
    assert response.headers["X-RateLimit-Remaining"] == str(LIMITE - 1)


# ---------- Comportamento do limitador ----------


def test_limitador_esquece_clientes_ociosos(relogio):
    limitador = LimitadorDeTaxa(limite=2, janela=10, agora=relogio)
    limitador.registrar("parado")

    relogio.avancar(11)
    limitador.registrar("ativo")

    assert limitador.clientes == 1


def test_limitador_informa_a_espera_ate_liberar(relogio):
    limitador = LimitadorDeTaxa(limite=1, janela=10, agora=relogio)
    limitador.registrar("cliente")

    relogio.avancar(4)
    veredito = limitador.registrar("cliente")

    assert veredito.permitido is False
    assert veredito.espera == pytest.approx(6.0)
